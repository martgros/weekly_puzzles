"""Monte Carlo validation for multi-period production planning solutions.

This script validates optimization results by simulating the production plan
using Monte Carlo sampling from the demand distributions.
"""

import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
from multi_period_solver import MultiPeriodProductionSolver, OptimizationMode


def truncated_normal_sample(
    mean: float, std: float, lower: float, upper: float, size: int
) -> np.ndarray:
    """Sample from a truncated normal distribution.

    Args:
        mean: Mean of the normal distribution.
        std: Standard deviation.
        lower: Lower truncation bound.
        upper: Upper truncation bound.
        size: Number of samples.

    Returns:
        Array of samples from the truncated normal distribution.
    """
    a = (lower - mean) / std
    b = (upper - mean) / std
    return stats.truncnorm.rvs(a, b, loc=mean, scale=std, size=size)


def simulate_production_plan(
    production_plan: dict[tuple[int, int], float],
    demand_means: dict[int, list[float]],
    initial_inventory: dict[int, float],
    num_simulations: int = 100000,
    seed: int = 42,
) -> np.ndarray:
    """Simulate production plan profits using Monte Carlo.

    Args:
        production_plan: Dict mapping (product, period) to production quantity.
        demand_means: Dict mapping product to list of demand means per period.
        initial_inventory: Dict mapping product to starting inventory.
        num_simulations: Number of Monte Carlo simulations.
        seed: Random seed for reproducibility.

    Returns:
        Array of simulated total profits.
    """
    np.random.seed(seed)

    # Problem parameters
    selling_prices = {1: 0.30, 2: 0.45}
    excess_costs = {1: 2.70, 2: 6.00}
    holding_costs = {1: 0.50, 2: 1.00}
    num_periods = 3
    base_std = 0.1
    std_increment = 0.05

    # Pre-generate all noise samples for efficiency
    # noise[t][product] has shape (num_simulations,)
    noise = {}
    for t in range(num_periods):
        std_dev = base_std + std_increment * t
        for product in [1, 2]:
            noise[(t, product)] = truncated_normal_sample(1.0, std_dev, 0.0, 2.0, num_simulations)

    # Arrays to accumulate profits
    total_profits = np.zeros(num_simulations)

    # Simulate for each scenario
    inventory = {1: np.full(num_simulations, initial_inventory[1]),
                 2: np.full(num_simulations, initial_inventory[2])}

    for t in range(num_periods):
        period_profit = np.zeros(num_simulations)

        for product in [1, 2]:
            # Get production for this period
            production = production_plan[(product, t + 1)]

            # Actual demand = mean * noise
            actual_demand = demand_means[product][t] * noise[(t, product)]

            # Available = production + previous inventory
            available = production + inventory[product]

            # Sold = min(available, demand)
            sold = np.minimum(available, actual_demand)

            # Ending inventory
            ending_inventory = np.maximum(0, available - sold)

            # Revenue from sales
            revenue = sold * selling_prices[product]

            # Holding cost (for intermediate periods)
            if t < num_periods - 1:
                cost = ending_inventory * holding_costs[product]
            else:
                # Final period: excess cost for remaining inventory
                cost = ending_inventory * excess_costs[product]

            period_profit += revenue - cost
            inventory[product] = ending_inventory

        total_profits += period_profit

    return total_profits


def calculate_cvar(profits: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
    """Calculate VaR and CVaR at given alpha level.

    Args:
        profits: Array of profit values.
        alpha: Tail probability (e.g., 0.05 for 5%).

    Returns:
        Tuple of (VaR, CVaR).
    """
    var = np.percentile(profits, alpha * 100)
    cvar = profits[profits <= var].mean()
    return var, cvar


def main():
    """Run Monte Carlo validation for multi-objective solution."""
    print("=" * 70)
    print("Monte Carlo Validation: Multi-Objective Production Plan")
    print("=" * 70)

    # Step 1: Get the optimized production plan from the solver
    print("\n1. Running multi-objective optimization to get production plan...")
    solver = MultiPeriodProductionSolver(
        initial_inventory={1: 7000, 2: 10500},
        number_scenarios=10000,
        time_limit=15,
    )
    result = solver.solve(OptimizationMode.MULTI_OBJECTIVE)

    # Extract production plan
    production_plan = result['solution']
    print("\nProduction Plan from Multi-Objective Optimization:")
    print("-" * 50)
    for t in range(3):
        p1 = production_plan[(1, t + 1)]
        p2 = production_plan[(2, t + 1)]
        print(f"  Period {t + 1}: Product 1 = {p1:,.0f}, Product 2 = {p2:,.0f}")

    print(f"\nOptimization Results:")
    print(f"  Expected Profit: ${result['expected_profit']:,.2f}")
    print(f"  VaR 5%: ${result['var_5']:,.2f}")
    print(f"  CVaR 5%: ${result['cvar_5']:,.2f}")

    # Step 2: Run Monte Carlo simulation
    print("\n2. Running Monte Carlo simulation (100,000 scenarios)...")
    num_simulations = 100000
    simulated_profits = simulate_production_plan(
        production_plan=production_plan,
        demand_means=solver.demand_means,
        initial_inventory=solver.initial_inventory,
        num_simulations=num_simulations,
        seed=42,
    )

    # Step 3: Calculate statistics
    mc_mean = np.mean(simulated_profits)
    mc_std = np.std(simulated_profits)
    mc_var, mc_cvar = calculate_cvar(simulated_profits, alpha=0.05)

    print("\n3. Monte Carlo Simulation Results:")
    print("-" * 50)
    print(f"  Number of simulations: {num_simulations:,}")
    print(f"  Mean Profit: ${mc_mean:,.2f}")
    print(f"  Std Profit: ${mc_std:,.2f}")
    print(f"  Min Profit: ${np.min(simulated_profits):,.2f}")
    print(f"  Max Profit: ${np.max(simulated_profits):,.2f}")
    print(f"  VaR 5%: ${mc_var:,.2f}")
    print(f"  CVaR 5%: ${mc_cvar:,.2f}")

    # Step 4: Compare with optimization results
    print("\n4. Comparison: Optimization vs Monte Carlo")
    print("-" * 50)
    print(f"  Expected Profit: ${result['expected_profit']:,.2f} vs ${mc_mean:,.2f} "
          f"(diff: {100 * (mc_mean - result['expected_profit']) / result['expected_profit']:+.2f}%)")
    print(f"  VaR 5%:          ${result['var_5']:,.2f} vs ${mc_var:,.2f} "
          f"(diff: {100 * (mc_var - result['var_5']) / abs(result['var_5']):+.2f}%)")
    print(f"  CVaR 5%:         ${result['cvar_5']:,.2f} vs ${mc_cvar:,.2f} "
          f"(diff: {100 * (mc_cvar - result['cvar_5']) / abs(result['cvar_5']):+.2f}%)")

    # Step 5: Plot histogram
    print("\n5. Generating histogram plot...")
    fig, ax = plt.subplots(figsize=(12, 6))

    # Histogram
    n, bins, patches = ax.hist(simulated_profits, bins=100, density=True,
                                alpha=0.7, color='#9b59b6', edgecolor='black',
                                label='Monte Carlo Distribution')

    # KDE overlay
    sns.kdeplot(simulated_profits, ax=ax, color='purple', linewidth=2,
                label='KDE Estimate')

    # Add vertical lines for key statistics
    ax.axvline(mc_mean, color='green', linewidth=2, linestyle='-',
               label=f'Mean: ${mc_mean:,.0f}')
    ax.axvline(mc_var, color='orange', linewidth=2, linestyle='--',
               label=f'VaR 5%: ${mc_var:,.0f}')
    ax.axvline(mc_cvar, color='red', linewidth=2, linestyle='--',
               label=f'CVaR 5%: ${mc_cvar:,.0f}')
    ax.axvline(0, color='black', linewidth=1.5, linestyle=':',
               label='Break-even')

    # Mark optimization results with diamonds
    ax.scatter([result['expected_profit']], [1e-3], marker='D', s=150,
               color='green', edgecolors='black', linewidths=2, zorder=10,
               label=f"Opt E[P]: ${result['expected_profit']:,.0f}")
    ax.scatter([result['cvar_5']], [1e-3], marker='D', s=150,
               color='red', edgecolors='black', linewidths=2, zorder=10,
               label=f"Opt CVaR: ${result['cvar_5']:,.0f}")

    ax.set_xlabel('Total Profit ($)', fontsize=12)
    ax.set_ylabel('Density', fontsize=12)
    ax.set_title('Monte Carlo Validation: Multi-Objective Production Plan\n'
                 f'(n={num_simulations:,} simulations)', fontsize=14)
    ax.legend(loc='upper left', fontsize=9)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.yscale("log")
    plt.xlim(left=-5000)
    plt.ylim(bottom=1e-8,top=1e-2)
    plt.savefig('monte_carlo_validation.png', dpi=150, bbox_inches='tight')
    plt.show()

    print("\nPlot saved to 'monte_carlo_validation.png'")
    print("=" * 70)


if __name__ == "__main__":
    main()
