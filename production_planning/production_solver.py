"""Production planning solver using InsideOpt Seeker.

This module provides a class-based implementation for solving the production
planning optimization problem with different optimization modes.
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import seeker as skr
from seeker_utils import get_license_path


class OptimizationMode(Enum):
    """Available optimization modes for the production planning problem."""

    DETERMINISTIC = "deterministic"
    MAXIMIZE_EXPECTED_PROFIT = "maximize_expected_profit"
    MAXIMIZE_CVAR = "maximize_CVaR"
    MULTI_OBJECTIVE = "multi_objective"


class ProductionSolver:
    """Solver for the production planning problem under uncertainty.

    This class handles the production planning optimization problem where
    a company must decide how much of two products to produce given uncertain
    demand. The solver supports multiple optimization modes including expected
    profit maximization and risk-aware objectives.

    Args:
        number_scenarios: Number of scenarios for stochastic optimization.
        seed: Random seed for reproducibility.
        time_limit: Time limit in seconds for optimization.
        fair_exp_profit: Fair threshold for expected profit in multi-objective mode.
        fair_cvar: Fair threshold for CVaR in multi-objective mode.
        excellent_exp_profit: Excellent threshold for expected profit in multi-objective mode.
        excellent_cvar: Excellent threshold for CVaR in multi-objective mode.
    """

    def __init__(
        self,
        number_scenarios: int = 1000,
        seed: int = 19887,
        time_limit: int = 15,
        fair_exp_profit: float = 5400.0,
        fair_cvar: float = 3000.0,
        excellent_exp_profit: float = 5554.0,
        excellent_cvar: float = 4000.0,
    ):
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

    def solve(self, mode: OptimizationMode) -> dict:
        """Solve the production planning problem with the specified mode.

        Creates a fresh Seeker environment, builds the optimization model,
        and solves it according to the specified optimization mode.

        Args:
            mode: The optimization mode to use.

        Returns:
            A dictionary containing:
                - expected_profit: The expected profit value
                - solution: List of production quantities [q1, q2]
                - var_5: Value at Risk at 5%
                - cvar_5: Conditional Value at Risk at 5%

        Raises:
            ValueError: If an unknown optimization mode is provided.
        """
        env = skr.Env(self.lic_path, stochastic=True)
        env.seed(self.seed)
        env.set_stochastic_parameters(self.number_scenarios, 0)

        # Decision variables: production quantities for products 1 and 2
        x = [env.ordinal(0, 20000, 6000), env.ordinal(0, 20000, 10500)]

        # Stochastic demand with normal distribution noise
        noise = [env.normal(1, 0.1, 0, 2) for _ in range(2)]
        demand = [7000 * noise[0], 10500 * noise[1]]

        # Sold and excess quantities
        sold = [env.min([x[i], demand[i]]) for i in range(2)]
        excess = [env.max_0(x[i] - sold[i]) for i in range(2)]

        # Constraints
        env.enforce_leq(3 * x[0] + 4 * x[1], 60000)
        env.enforce_leq(x[0] + x[1], 18000)

        # Profit calculation
        profit = 0.3 * sold[0] + 0.45 * sold[1] - 2.7 * excess[0] - 6.0 * excess[1]
        exp_profit = env.aggregate_mean(profit)

        # Risk measures
        var_5 = env.aggregate_quantile(profit, 0.05, False)
        # manual CVaR calculation based on definition (not needed since seeker provides a built-in method):
        #percentage_lower = env.aggregate_mean(profit < var_5)
        #delta = (0.05 * self.number_scenarios - percentage_lower * self.number_scenarios) * var_5
        #cvar_5 = (
        #    env.aggregate_mean((profit < var_5) * profit) * self.number_scenarios + delta
        #) / (self.number_scenarios * 0.05)
        # seeker now provides a built-in method to calculate CVaR directly:
        cvar_5 = env.aggregate_cvar(profit, 0.05, False)

        env.set_report(self.time_limit / 4)

        # Execute optimization based on mode
        self._run_optimization(env, mode, exp_profit, cvar_5)

        # Extract results
        result = {
            "expected_profit": exp_profit.get_value(),
            "solution": [v.get_value() for v in x],
            "var_5": var_5.get_value(),
            "cvar_5": cvar_5.get_value(),
        }

        # Store profit samples in results DataFrame
        column_name = f"profit_{mode.value}"
        self.results[column_name] = profit.get_values()
        self._solutions[mode.value] = result

        print(
            f"Mode: {mode.value}\n"
            f"  Solution: {result['solution']}\n"
            f"  Expected Profit: {result['expected_profit']:.2f}\n"
            f"  VaR 5%: {result['var_5']:.2f}\n"
            f"  CVaR 5%: {result['cvar_5']:.2f}"
        )

        env.end()
        return result

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
            '''
            multi_objective(objectives, fair, excellent, directionMax, time)
            - Optimizes target terms ”objectives” for ”time” seconds.
            - The direction of the optimization of respective objective is maximization if
              corresponding entry in ”directionMax” is true.
            - For each objective, the respective values in ”fair” and ”excellent” must not be
              equal and be in the correct order.
            - For an objective to be maximized, that value in ”excellent” is expected to be strictly
              greater than that in ”fair. (for minimization it must be strictly lower)
            - seeker will still aim to get all objectives into ’fair’ territory first, then striving for "excellent" territory. The optimization will stop when either all objectives are in "excellent" territory or the time limit is reached.
            '''
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
        title: str = "Profit Distribution by Optimization Mode",
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
            plt.xlim(left=-5000)
            plt.ylim(bottom=1e-8)

        plt.xlabel("Profit")
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
                summary_data.append({
                    "mode": mode_name,
                    "q1": result["solution"][0],
                    "q2": result["solution"][1],
                    "expected_profit": result["expected_profit"],
                    "var_5": result["var_5"],
                    "cvar_5": result["cvar_5"],
                    "mean_profit": profit_data.mean(),
                    "std_profit": profit_data.std(),
                    "min_profit": profit_data.min(),
                    "max_profit": profit_data.max(),
                })

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
    # Example usage
    solver = ProductionSolver(number_scenarios=10000, time_limit=15)

    # Solve with different modes
    solver.solve(OptimizationMode.DETERMINISTIC)
    solver.solve(OptimizationMode.MAXIMIZE_EXPECTED_PROFIT)

    # Show summary
    print("\n" + "=" * 60)
    print("Summary:")
    print(solver.get_summary().to_string())

    # Plot distributions
    solver.plot_profit_distribution()
