# Multi-Period Production Planning Under Uncertainty

This is an extension of the single-period production planning problem to a multi-period setting with time-varying demand forecasts.

## Problem Overview

A company produces two products and must plan production over a **3-period planning horizon**. Demand for each product is uncertain and varies over time according to a probabilistic forecast.

## Products and Economics

| Product | Selling Price ($) | Holding Cost ($/unit/period) | Excess Cost ($/unit) |
|---------|-------------------|------------------------------|----------------------|
| 1       | 0.30              | 0.50                         | 2.70                 |
| 2       | 0.45              | 1.00                         | 6.00                 |

**Note:** Holding costs are charged per period for inventory carried forward. Excess costs apply only to leftover inventory at the end of the final period.

## Initial Inventory

| Product | Initial Inventory (units) |
|---------|---------------------------|
| 1       | 7,000                     |
| 2       | 10,500                    |

## Demand Forecast

Demand is modeled as a multiplicative noise model where actual demand equals the forecast mean multiplied by a random factor:

$$D_{i,t} = \mu_{i,t} \cdot \epsilon_{i,t}$$

where $\epsilon_{i,t} \sim \text{Normal}(1, \sigma_t)$ truncated to $[0, 2]$.

### Forecast Uncertainty Grows Over Time

The standard deviation increases linearly with the forecast horizon to reflect greater uncertainty for distant periods:

$$\sigma_t = 0.1 + 0.05 \cdot t$$

| Period | t | Standard Deviation ($\sigma_t$) |
|--------|---|----------------------------------|
| 1      | 0 | 0.10                             |
| 2      | 1 | 0.15                             |
| 3      | 2 | 0.20                             |

This models the realistic behavior that forecasts become less reliable further into the future.

### Forecast Mean Values by Period

| Product | Period 1 | Period 2 | Period 3 |
|---------|----------|----------|----------|
| 1       | 7,000    | 6,000    | 5,000    |
| 2       | 10,500   | 9,000    | 10,000   |

## Decision Variables

For each period $t \in \{1, 2, 3\}$ and product $i \in \{1, 2\}$:

- $q_{i,t}$: Quantity of product $i$ to produce in period $t$
- $s_{i,t}$: Quantity of product $i$ sold in period $t$
- $I_{i,t}$: Ending inventory of product $i$ at the end of period $t$

## Constraints

### Production Capacity (per period)

$$3 q_{1,t} + 4 q_{2,t} \le 60000 \quad \forall t$$

$$q_{1,t} + q_{2,t} \le 18000 \quad \forall t$$

### Inventory Carryover Dynamics

Available supply equals production plus inventory from the previous period:

$$A_{i,t} = q_{i,t} + I_{i,t-1} \quad \forall i, t$$

where $I_{i,0}$ is the initial inventory.

### Sales and Inventory Relationships

$$s_{i,t} = \min(A_{i,t}, D_{i,t}) \quad \forall i, t$$

$$I_{i,t} = \max(0, A_{i,t} - s_{i,t}) \quad \forall i, t$$

### Non-negativity

$$q_{i,t}, s_{i,t}, I_{i,t} \ge 0 \quad \forall i, t$$

## Objective

Maximize total expected profit over the planning horizon, accounting for revenue, holding costs, and excess costs:

$$\max \mathbb{E}\left[ \sum_{t=1}^{3} \left( \sum_{i=1}^{2} p_i \cdot s_{i,t} - h_i \cdot I_{i,t} \right) - \sum_{i=1}^{2} c_i \cdot I_{i,T} \right]$$

where:
- $p_i$ is the selling price of product $i$
- $h_i$ is the holding cost of product $i$ per period
- $c_i$ is the excess cost of product $i$ (applied only to final period inventory $I_{i,T}$)

## Implementation Requirements

### Stochastic Optimization Setup

```python
# Time horizon
T = 3

# Demand forecast means
demand_means = {
    1: [7000, 6000, 5000],  # Product 1 forecast
    2: [10500, 9000, 10000],  # Product 2 forecast
}

# Initial inventory
initial_inventory = {1: 7000, 2: 10500}

# Noise model with increasing uncertainty over horizon
# noise ~ Normal(mean=1, std=0.1 + 0.05*t) truncated to [0, 2]
noise = [[env.normal(1, 0.1 + 0.05 * t, 0, 2) for _ in range(2)] for t in range(T)]

# Actual demand per period
demand = [[demand_means[i+1][t] * noise[t][i] for i in range(2)] for t in range(T)]
```

### Optimization Modes to Implement

1. **Deterministic**: Evaluate at initial solution
2. **Maximize Expected Profit**: Optimize $\mathbb{E}[\text{Profit}]$
3. **Maximize CVaR**: Risk-aware optimization using CVaR at 5%
4. **Multi-Objective**: Balance expected profit and CVaR

## Deliverables

Create a solver class `MultiPeriodProductionSolver` that:

1. Accepts the planning horizon, demand forecasts, and initial inventory as parameters
2. Builds the multi-period stochastic optimization model with inventory carryover
3. Supports all four optimization modes
4. Returns:
   - Optimal production quantities for each product and period
   - Expected total profit
   - VaR and CVaR risk measures
   - Profit distribution samples
   - Expected ending inventory per period

## Key Differences from Single-Period Problem

| Aspect | Single-Period | Multi-Period |
|--------|---------------|--------------|
| Time horizon | 1 period | 3 periods |
| Demand | Single distribution per product | Time-varying forecast |
| Decision variables | 2 (one per product) | 6 (product × period) |
| Inventory | No carryover | Carryover between periods |
| Costs | Excess cost only | Holding costs + final excess cost |
| Constraints | Applied once | Applied per period |
| Objective | Single-period profit | Sum of profits over horizon |

## Hints

- Inventory carryover links decisions across periods, so earlier production decisions affect later opportunities
- The stochastic noise can be correlated or independent across periods
- Initial inventory provides a buffer for uncertainty in early periods
- Holding costs discourage overproduction, while excess costs penalize leftover inventory at the end
