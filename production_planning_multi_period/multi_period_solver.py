"""Multi-period production planning solver using InsideOpt Seeker.

This module extends the single-period production planning problem to handle
multiple time periods with time-varying demand forecasts.
"""

import sys
from enum import Enum
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import seeker as skr
from seeker_utils import get_license_path


class OptimizationMode(Enum):
    """Available optimization modes for the production planning problem."""

    DETERMINISTIC = "deterministic"
    MAXIMIZE_EXPECTED_PROFIT = "maximize_expected_profit"
    MAXIMIZE_CVAR = "maximize_CVaR"
    MULTI_OBJECTIVE = "multi_objective"


class MultiPeriodProductionSolver:
    """Solver for the multi-period production planning problem under uncertainty.

    This class handles the production planning optimization problem where
    a company must decide how much of two products to produce over multiple
    periods given uncertain, time-varying demand forecasts.

    Args:
        num_periods: Number of planning periods.
        demand_means: Dictionary mapping product index (1 or 2) to list of
            demand means for each period.
        initial_inventory: Dictionary mapping product index to starting inventory.
        number_scenarios: Number of scenarios for stochastic optimization.
        seed: Random seed for reproducibility.
        time_limit: Time limit in seconds for optimization.
        fair_exp_profit: Fair threshold for expected profit in multi-objective mode.
        fair_cvar: Fair threshold for CVaR in multi-objective mode.
        excellent_exp_profit: Excellent threshold for expected profit in multi-objective mode.
        excellent_cvar: Excellent threshold for CVaR in multi-objective mode.
    """

    # Product parameters
    SELLING_PRICES = {1: 0.30, 2: 0.45}
    EXCESS_COSTS = {1: 2.70, 2: 6.00}  # Cost for unsold inventory at final period
    HOLDING_COSTS = {1: 0.50, 2: 1.00}  # Per-unit holding cost per period

    # Default demand forecasts
    DEFAULT_DEMAND_MEANS = {
        1: [7000, 6000, 5000],
        2: [10500, 9000, 10000],
    }

    # Initial inventory levels
    DEFAULT_INITIAL_INVENTORY = {1: 7000, 2: 10500}

    def __init__(
        self,
        num_periods: int = 3,
        demand_means: Optional[dict[int, list[float]]] = None,
        initial_inventory: Optional[dict[int, float]] = None,
        number_scenarios: int = 1000,
        seed: int = 19887,
        time_limit: int = 15,
        fair_exp_profit: float = 16000.0,
        fair_cvar: float = 9000.0,
        excellent_exp_profit: float = 16600.0,
        excellent_cvar: float = 12000.0,
    ):
        self.num_periods = num_periods
        self.demand_means = demand_means or self.DEFAULT_DEMAND_MEANS
        self.initial_inventory = initial_inventory or self.DEFAULT_INITIAL_INVENTORY
        self.number_scenarios = number_scenarios
        self.seed = seed
        self.time_limit = time_limit
        self.fair_exp_profit = fair_exp_profit
        self.fair_cvar = fair_cvar
        self.excellent_exp_profit = excellent_exp_profit
        self.excellent_cvar = excellent_cvar
        self.lic_path = get_license_path(from_notebook=False)
        self.results: pd.DataFrame = pd.DataFrame()
        self._solutions: dict[str, dict] = {}

        # Validate demand means
        for product, means in self.demand_means.items():
            if len(means) != num_periods:
                raise ValueError(
                    f"Product {product} has {len(means)} demand means, "
                    f"expected {num_periods}"
                )

    def solve(self, mode: OptimizationMode) -> dict:
        """Solve the multi-period production planning problem with the specified mode.

        Creates a fresh Seeker environment, builds the optimization model,
        and solves it according to the specified optimization mode.

        Args:
            mode: The optimization mode to use.

        Returns:
            A dictionary containing:
                - expected_profit: The expected total profit value
                - solution: Dict mapping (product, period) to production quantities
                - var_5: Value at Risk at 5%
                - cvar_5: Conditional Value at Risk at 5%
                - period_profits: Expected profit per period
                - expected_inventory: Expected ending inventory per period

        Raises:
            ValueError: If an unknown optimization mode is provided.
        """
        env = skr.Env(self.lic_path, stochastic=True)
        env.seed(self.seed)
        env.set_stochastic_parameters(self.number_scenarios, 0)

        # Decision variables: production quantities for each product and period
        # x[t][i] = production of product i in period t
        #
        # Initialize accounting for expected inventory flow across periods.
        # Use conservative estimates (variance_buffer * net demand) because:
        # 1. With stochastic demand, expected ending inventory > 0 even when
        #    production matches expected demand (due to min/max asymmetry)
        # 2. This creates a reasonable deterministic baseline that leaves room
        #    for optimization to find better solutions
        x: list[list[skr.Term]] = []
        expected_inv = [float(self.initial_inventory[1]), float(self.initial_inventory[2])]
        variance_buffer = 0.85  # Produce 85% of net demand to account for uncertainty

        for t in range(self.num_periods):
            # Production needed = (demand - expected inventory) * buffer
            init_prod = [
                max(0, (self.demand_means[i + 1][t] - expected_inv[i]) * variance_buffer)
                for i in range(2)
            ]
            period_vars = [
                env.ordinal(0, 20000, init_prod[0]),
                env.ordinal(0, 20000, init_prod[1]),
            ]
            x.append(period_vars)

            # Estimate expected ending inventory for next period
            # With buffer, we expect some small leftover inventory
            for i in range(2):
                available = init_prod[i] + expected_inv[i]
                # Conservative: assume we sell most but keep small buffer
                expected_inv[i] = max(0, available - self.demand_means[i + 1][t] * 0.95)

        # Stochastic demand with normal distribution noise per period
        # Uncertainty grows with forecast horizon: std_dev = 0.1 + 0.05 * t
        # noise[t][i] ~ Normal(1, std_dev(t)) truncated to [0, 2]
        base_std = 0.1
        std_increment = 0.05
        noise: list[list[skr.Term]] = []
        for t in range(self.num_periods):
            std_dev = base_std + std_increment * t
            period_noise = [env.normal(1, std_dev, 0, 2) for _ in range(2)]
            noise.append(period_noise)

        # Actual demand = mean * noise
        demand: list[list[skr.Term]] = []
        for t in range(self.num_periods):
            period_demand = [
                self.demand_means[i + 1][t] * noise[t][i] for i in range(2)
            ]
            demand.append(period_demand)

        # Inventory carryover dynamics and profit calculation
        # inventory[t][i] = ending inventory at end of period t for product i
        # available[t][i] = production[t][i] + inventory[t-1][i]
        # sold[t][i] = min(available[t][i], demand[t][i])
        # inventory[t][i] = available[t][i] - sold[t][i]

        inventory: list[list[skr.Term]] = []
        sold: list[list[skr.Term]] = []
        period_profits: list[skr.Term] = []

        for t in range(self.num_periods):
            # Constraints for this period
            env.enforce_leq(3 * x[t][0] + 4 * x[t][1], 60000)
            env.enforce_leq(x[t][0] + x[t][1], 18000)

            # Available supply = production + previous inventory
            if t == 0:
                available = [
                    x[t][i] + self.initial_inventory[i + 1] for i in range(2)
                ]
            else:
                available = [x[t][i] + inventory[t - 1][i] for i in range(2)]

            # Sales limited by available supply and demand
            period_sold = [env.min([available[i], demand[t][i]]) for i in range(2)]

            # Ending inventory = available - sold (always >= 0)
            period_inventory = [env.max_0(available[i] - period_sold[i]) for i in range(2)]

            # Revenue from sales
            revenue = (
                self.SELLING_PRICES[1] * period_sold[0]
                + self.SELLING_PRICES[2] * period_sold[1]
            )

            # Holding cost for inventory
            holding = (
                self.HOLDING_COSTS[1] * period_inventory[0]
                + self.HOLDING_COSTS[2] * period_inventory[1]
            )

            if t == self.num_periods - 1:
                # Final period: charge excess cost for leftover inventory
                excess_cost = (
                    self.EXCESS_COSTS[1] * period_inventory[0]
                    + self.EXCESS_COSTS[2] * period_inventory[1]
                )
                profit_t = revenue - holding - excess_cost
            else:
                profit_t = revenue - holding

            sold.append(period_sold)
            inventory.append(period_inventory)
            period_profits.append(profit_t)

        total_profit = env.sum(period_profits)
        exp_profit = env.aggregate_mean(total_profit)

        # Risk measures
        var_5 = env.aggregate_quantile(total_profit, 0.05, False)
        cvar_5 = env.aggregate_cvar(total_profit, 0.05, False)

        env.set_report(self.time_limit / 4)

        # Compute expected profit per period before optimization
        period_exp_profits_terms = [env.aggregate_mean(p) for p in period_profits]

        # Compute expected inventory per period for each product
        inventory_exp_terms = [
            [env.aggregate_mean(inventory[t][i]) for i in range(2)]
            for t in range(self.num_periods)
        ]

        # Execute optimization based on mode
        self._run_optimization(env, mode, exp_profit, cvar_5)

        # Extract results
        solution = {}
        for t in range(self.num_periods):
            for i in range(2):
                solution[(i + 1, t + 1)] = x[t][i].get_value()

        period_exp_profits = [p.get_value() for p in period_exp_profits_terms]

        expected_inventory = {
            (i + 1, t + 1): inventory_exp_terms[t][i].get_value()
            for t in range(self.num_periods)
            for i in range(2)
        }

        result = {
            "expected_profit": exp_profit.get_value(),
            "solution": solution,
            "var_5": var_5.get_value(),
            "cvar_5": cvar_5.get_value(),
            "period_profits": period_exp_profits,
            "expected_inventory": expected_inventory,
        }

        # Store profit samples in results DataFrame
        column_name = f"profit_{mode.value}"
        self.results[column_name] = total_profit.get_values()
        self._solutions[mode.value] = result

        self._print_solution(mode, result)

        env.end()
        return result

    def _print_solution(self, mode: OptimizationMode, result: dict) -> None:
        """Print formatted solution output.

        Args:
            mode: The optimization mode used.
            result: The result dictionary from solve().
        """
        print(f"\nMode: {mode.value}")
        print("-" * 60)
        print("Production Plan:")
        print(f"  {'Period':<8} {'Prod 1':<10} {'Prod 2':<10} {'Inv 1':<10} {'Inv 2':<10}")
        for t in range(self.num_periods):
            q1 = result["solution"][(1, t + 1)]
            q2 = result["solution"][(2, t + 1)]
            inv1 = result["expected_inventory"][(1, t + 1)]
            inv2 = result["expected_inventory"][(2, t + 1)]
            print(f"  {t + 1:<8} {q1:<10.0f} {q2:<10.0f} {inv1:<10.0f} {inv2:<10.0f}")
        print()
        print("Expected Profits by Period:")
        for t, profit in enumerate(result["period_profits"]):
            print(f"  Period {t + 1}: ${profit:,.2f}")
        print()
        print(f"Total Expected Profit: ${result['expected_profit']:,.2f}")
        print(f"VaR 5%: ${result['var_5']:,.2f}")
        print(f"CVaR 5%: ${result['cvar_5']:,.2f}")

    def _run_optimization(
        self,
        env: skr.Env,
        mode: OptimizationMode,
        exp_profit: skr.Term,
        cvar: skr.Term,
    ) -> None:
        """Run the optimization based on the selected mode.

        Args:
            env: The Seeker environment.
            mode: The optimization mode.
            exp_profit: The expected profit term.
            cvar: The CVaR term.

        Raises:
            ValueError: If an unknown optimization mode is provided.
        """
        if mode == OptimizationMode.DETERMINISTIC:
            print("\nEvaluating deterministically...")
            env.evaluate()
        elif mode == OptimizationMode.MAXIMIZE_EXPECTED_PROFIT:
            print("\nOptimizing expected profit...")
            env.maximize(exp_profit, self.time_limit)
        elif mode == OptimizationMode.MAXIMIZE_CVAR:
            print("\nOptimizing CVaR...")
            env.maximize(cvar, self.time_limit)
        elif mode == OptimizationMode.MULTI_OBJECTIVE:
            print("\nOptimizing multi-objective (expected profit + CVaR)...")
            env.multi_objective(
                [exp_profit, cvar],
                [self.fair_exp_profit, self.fair_cvar],
                [self.excellent_exp_profit, self.excellent_cvar],
                [True, True],
                self.time_limit,
            )
            env.evaluate()
        else:
            raise ValueError(f"Unknown optimization mode: {mode}")

    def solve_all(self, modes: Optional[list[OptimizationMode]] = None) -> pd.DataFrame:
        """Solve the problem with multiple optimization modes.

        Args:
            modes: List of modes to solve. Defaults to deterministic and
                   maximize expected profit.

        Returns:
            DataFrame containing profit samples for all solved modes.
        """
        if modes is None:
            modes = [
                OptimizationMode.DETERMINISTIC,
                OptimizationMode.MAXIMIZE_EXPECTED_PROFIT,
            ]

        for mode in modes:
            self.solve(mode)

        return self.results

    def plot_profit_distribution(
        self,
        figsize: tuple[int, int] = (10, 6),
        log_scale: bool = True,
        title: str = "Multi-Period Profit Distribution by Optimization Mode",
    ) -> None:
        """Plot the profit distributions using kernel density estimation.

        Args:
            figsize: Figure size as (width, height).
            log_scale: Whether to use logarithmic y-axis scale.
            title: Plot title.

        Raises:
            ValueError: If no results are available to plot.
        """
        if self.results.empty:
            raise ValueError("No results to plot. Run solve() first.")

        plt.figure(figsize=figsize)
        sns.kdeplot(data=self.results, fill=True)

        if log_scale:
            plt.yscale("log")
            plt.xlim(left=-15000)
            plt.ylim(bottom=1e-8)

        plt.xlabel("Total Profit ($)")
        plt.ylabel("Density")
        plt.title(title)
        plt.tight_layout()
        plt.show()

    def get_summary(self) -> pd.DataFrame:
        """Get a summary of all solved modes.

        Returns:
            DataFrame with summary statistics for each solved mode.
        """
        if not self._solutions:
            return pd.DataFrame()

        summary_data = []
        for mode_name, result in self._solutions.items():
            column_name = f"profit_{mode_name}"
            if column_name in self.results.columns:
                profit_data = self.results[column_name]
                row = {
                    "mode": mode_name,
                    "expected_profit": result["expected_profit"],
                    "var_5": result["var_5"],
                    "cvar_5": result["cvar_5"],
                    "mean_profit": profit_data.mean(),
                    "std_profit": profit_data.std(),
                    "min_profit": profit_data.min(),
                    "max_profit": profit_data.max(),
                }
                # Add production quantities per period
                for t in range(self.num_periods):
                    row[f"q1_t{t + 1}"] = result["solution"][(1, t + 1)]
                    row[f"q2_t{t + 1}"] = result["solution"][(2, t + 1)]
                # Add expected inventory per period
                for t in range(self.num_periods):
                    row[f"inv1_t{t + 1}"] = result["expected_inventory"][(1, t + 1)]
                    row[f"inv2_t{t + 1}"] = result["expected_inventory"][(2, t + 1)]
                summary_data.append(row)

        return pd.DataFrame(summary_data)

    def clear_results(self) -> None:
        """Clear all stored results."""
        self.results = pd.DataFrame()
        self._solutions = {}

    def set_multi_objective_params(
        self,
        fair_exp_profit: Optional[float] = None,
        fair_cvar: Optional[float] = None,
        excellent_exp_profit: Optional[float] = None,
        excellent_cvar: Optional[float] = None,
    ) -> None:
        """Set multi-objective optimization parameters.

        Only updates parameters that are explicitly provided.

        Args:
            fair_exp_profit: Fair threshold for expected profit.
            fair_cvar: Fair threshold for CVaR.
            excellent_exp_profit: Excellent threshold for expected profit.
            excellent_cvar: Excellent threshold for CVaR.
        """
        if fair_exp_profit is not None:
            self.fair_exp_profit = fair_exp_profit
        if fair_cvar is not None:
            self.fair_cvar = fair_cvar
        if excellent_exp_profit is not None:
            self.excellent_exp_profit = excellent_exp_profit
        if excellent_cvar is not None:
            self.excellent_cvar = excellent_cvar


if __name__ == "__main__":
    print("=" * 60)
    print("Multi-Period Production Planning with Inventory Carryover")
    print("=" * 60)

    # Display problem setup
    print("\nDemand Forecast (means by period):")
    print("  Product 1: [7000, 6000, 5000]")
    print("  Product 2: [10500, 9000, 10000]")
    print("\nNoise model: Normal(1, std_dev) truncated to [0, 2]")
    print("  Std dev increases with horizon: 0.1 + 0.05*t")
    print("  Period 1: std=0.10, Period 2: std=0.15, Period 3: std=0.20")
    print("\nInventory Dynamics:")
    print("  - Excess production carries over to next period")
    print("  - Holding costs: Product 1 = $0.50/unit, Product 2 = $1.00/unit")
    print("  - Excess cost at final period: Product 1 = $2.70/unit, Product 2 = $6.00/unit")

    # Create solver and run
    solver = MultiPeriodProductionSolver(
        num_periods=3,
        number_scenarios=10000,
        time_limit=15,
    )

    # Solve with different modes
    solver.solve(OptimizationMode.DETERMINISTIC)
    solver.solve(OptimizationMode.MAXIMIZE_EXPECTED_PROFIT)
    solver.solve(OptimizationMode.MAXIMIZE_CVAR)

    # Show summary
    print("\n" + "=" * 60)
    print("Summary of All Modes:")
    print("=" * 60)
    summary = solver.get_summary()
    print(summary.to_string())

    # Plot distributions
    solver.plot_profit_distribution()
