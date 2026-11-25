# Well Control Basics for Drillers (synthetic text written for tests)

<!-- page 41 -->
## Chapter 3. Pressure in the Wellbore

While a well is being drilled, the hole is filled with drilling fluid, usually called mud. Mud carries the cuttings to the surface, cools the bit and, most importantly, balances the pressure of the fluids in the rock. If the mud pressure falls below the pore pressure of a permeable formation, formation fluid may flow into the wellbore. Such an unwanted inflow is called a kick.

### 3.1 Hydrostatic Pressure

Hydrostatic pressure is the pressure exerted by a column of fluid at rest. It depends only on the density of the fluid and on the true vertical depth; it does not depend on the diameter of the hole or on its inclination. In oilfield units it is calculated as

$$p_h = 0.052 \, \rho \, D \tag{3.1}$$

where $p_h$ is the hydrostatic pressure, psi; $\rho$ is the mud density, lb/gal (ppg); $D$ is the true vertical depth, ft.

For fresh water with a density of 8.33 ppg the pressure gradient is about 0.433 psi/ft. Most drilling muds are heavier than water, although in some areas air or foam is used in-
<!-- page 42 -->
stead of mud.

### 3.2 The Mud Window

The mud density must satisfy two conditions at the same time. The mud pressure has to be higher than the pore pressure, otherwise the well may kick. It also has to be lower than the fracture pressure, otherwise the rock breaks down and mud is lost into the formation. The range between these two limits is called the mud window.

In deep water the window is often narrow, sometimes less than 0.5 ppg. In such wells casing has to be set at shorter intervals. Casing is a steel pipe that is run into the hole and cemented; it isolates the upper, weaker rocks from the heavier mud that is needed below.

Table 3.1. Pressure limits in the example well

| Depth, ft | Pore pressure, ppg | Fracture pressure, ppg |
| --- | --- | --- |
| 3,000 | 8.6 | 12.5 |
| 6,000 | 9.0 | 14.0 |
| 10,000 | 11.8 | 16.2 |

Fig. 3.1. Pore pressure, fracture pressure and mud density versus depth in the example well.

----
━━━ FORMAT 6: XY PLOT ━━━
The plot shows three curves versus depth. Pore pressure rises sharply below 8,500 ft and reaches 13 ppg.
KEYWORDS: pore pressure, mud window
----

<!-- page 43 -->
Well Control Basics for Drillers

### 3.3 Circulation and Equivalent Circulating Density

When the pumps are running, the mud moves down the drill pipe and back up the annulus, i.e. the space between the pipe and the wall of the hole. Friction in the annulus adds to the hydrostatic pressure, so the pressure on bottom is higher while circulating than with the pumps off. The sum is usually expressed as the equivalent circulating density (ECD).

$$\text{ECD} = \rho + \frac{\Delta p_a}{0.052 \, D} \tag{3.2}$$

where $\Delta p_a$ is the friction pressure loss in the annulus, psi.

A well that is stable while circulating may therefore start to flow when the pumps are stopped for a connection. Drillers call this connection gas if only small amounts of gas appear at surface.

**Example 3.1.** A well is 10,000 ft deep (true vertical depth) and is filled with 12.0 ppg mud. The friction pressure loss in the annulus is 260 psi. Find the hydrostatic pressure and the ECD.

Solution. The hydrostatic pressure is 0.052 × 12.0 × 10,000 = 6,240 psi. The ECD is 12.0 + 260 / (0.052 × 10,000) = 12.5 ppg.

<!-- page 44 -->
### 3.4 Kick Warning Signs

The most reliable sign of a kick is an increase in the volume of mud in the pits, which is called a pit gain. Mud that leaves the well must have been pushed out by something that entered it. Another positive sign is flow from the well with the pumps off.

Other signs are only warnings, because they may have other causes:

- a sudden increase in the drilling rate (a drilling break), which may simply mean softer rock;
- a decrease in pump pressure, which can also be caused by a washout in the pipe;
- gas in the mud, which may come from the drilled rock itself.

A falling pit level points the other way: mud is being lost into the formation. Losses are dangerous too. As the level in the annulus drops, the hydrostatic pressure decreases and the well may kick from another zone.

### 3.5 Behaviour of Gas

Gas is lighter than mud and migrates upward. If the well is open, the gas expands as it rises, slowly at first and very rapidly near the surface. A pit gain of 10 bbl on bottom may become more than 100 bbl near the surface.

If the well is shut in, the gas cannot expand. It keeps nearly the same pressure and carries it upward, so that the pressure increases in the whole wellbore, both at the surface and at the bottom. Unless the pressure is bled off in a controlled way, the weakest rock below the casing shoe may eventually be fractured. Here the simple model neglects gas solubility and temperature; in oil-based mud a large part of the gas may dissolve, and the kick is then hard to detect.

<!-- page 45 -->
### 3.6 Shutting In the Well

When a kick is detected, the crew stops drilling, raises the bit off bottom, stops the pumps, checks for flow and closes the blowout preventer (BOP). The BOP is a set of valves installed on the wellhead. After the pressures have stabilized, the shut-in drill pipe pressure (SIDPP) is read. It shows by how much the formation pressure exceeds the hydrostatic pressure of the mud in the pipe.

The density required to balance the formation, the kill mud weight, is

$$\rho_k = \rho + \frac{\text{SIDPP}}{0.052 \, D} \tag{3.3}$$

**Example 3.2.** A 10,000 ft well with 12.0 ppg mud is shut in. The SIDPP is 520 psi. Find the kill mud weight.

Solution. The required increase is 520 / (0.052 × 10,000) = 1.0 ppg. The kill mud weight is 13.0 ppg.

In the early days of drilling crews often relied on cable tools and had no blowout preventers; wells that met high pressure commonly blew out.

### Problems

1. A vertical well is 8,000 ft deep. The pore pressure on bottom is equivalent to 10.0 ppg. What is the lowest mud density that balances the formation, and what is the pressure on bottom?

2. During a connection the pit level rises by 5 bbl and the well keeps flowing. Explain what has happened and what the crew should do.

3. Using Table 3.1 and Fig. 3.1, choose the casing setting depths for the example well.
