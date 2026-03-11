# Production Planning

solving the problem as formulated in a deterministic way would lead to:
- s1=q1=6000
- s2=q2=10500
- e1=e2=0

Obviously, that would never hold in reality, because the demand is never known 100% deterministically.

Therefore the problem is reformulated in a stochastic optimization problem, using some assumption on the uncertainty (distribution) of the demand

$$
\text{Maximize }\;
0.3 s_1 + 0.45 s_2 - 2.70 e_1 - 6.00 e_2
$$
s.t.

$$
3 q_1 + 4 q_2 \le 60000
$$

$$
q_1 + q_2 \le 18000
$$

$$
s_1 \le q_1
$$

$$
s_1 \le D_1 \text{ with } D_1 \in 7000 * noise1
$$

$$
s_2 \le q_2
$$

$$
s_2 \le D_2 \text{ with } D_2 \in 10500 * noise2
$$

$$
e_1 \ge q_1 - s_1
$$

$$
e_2 \ge q_2 - s_2
$$

$$
e,\; q,\; s \ge 0
$$

noise1 and noise2 are assumed as normal distributions