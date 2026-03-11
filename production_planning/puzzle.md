# Production Planning

- Quantity of products 1 and 2 that you produce q1,q2
- The total sold products s1, s2
- excess of each product, i.e. products that you produced too much and they are not sold e1 and e2

| product | selling price $ | excess cost $ |
| ------- | --------------- | ------------- |
|1|0.3|2.7|
|2|0.45|6.0|

The optimization problem is:

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
s_1 \le 7000
$$

$$
s_2 \le q_2
$$

$$
s_2 \le 10500
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