# Damped Pendulum Simulation Example

This example demonstrates the mathematical modeling and visualization of a damped pendulum using the plotter application. It showcases physics simulation, data analysis, and comprehensive project organization.

## Overview

The simulation models a pendulum with the following physics:
- **Length**: 1.0 meter
- **Damping**: Variable coefficient (0.0 to 0.5)
- **Initial angle**: 60 degrees (π/3 radians)
- **Gravity**: 9.81 m/s²

## Mathematical Model

The damped pendulum follows the differential equation:
```
θ̈ + 2γθ̇ + (g/L)sin(θ) = 0
```

Where:
- θ: Angular displacement from vertical
- γ: Damping coefficient
- g: Gravitational acceleration (9.81 m/s²)
- L: Pendulum length (1.0 m)

## Files Created

### 1. `create_pendulum_simulation.py`
The main script that generates a complete project file with:
- **Datasets**: Multiple simulations with different damping coefficients
- **Charts**: Angle plots, phase portraits, energy analysis, trajectory plots
- **Notes**: Theoretical background and analysis results
- **Organized structure**: Folders for simulations, analysis, and theory

### 2. `demo_pendulum.py`
A quick demonstration script that:
- Runs a single simulation
- Creates basic matplotlib visualizations
- Generates the full project file
- Provides an overview of the results

## How to Use

### Quick Demo
```bash
cd examples
python demo_pendulum.py
```

This will:
1. Run a simulation and display basic plots
2. Create `pendulum_simulation.pplot` project file
3. Save `pendulum_demo.png` with visualization

### In the Plotter Application
1. Run the demo script first to generate the project file
2. Open the plotter application
3. Load `pendulum_simulation.pplot`
4. Explore the organized project structure

## Project Structure

The generated project contains:

```
📁 Simulations
  📊 Main Simulation (γ=0.1)
  📁 Parameter Study
    📊 Damping γ=0.00
    📊 Damping γ=0.05
    📊 Damping γ=0.10
    📊 Damping γ=0.20
    📊 Damping γ=0.50

📁 Analysis
  📊 Amplitude Envelope
  📈 Angle vs Time
  📈 Phase Portrait
  📈 Energy Analysis
  📈 Pendulum Trajectory
  📝 Simulation Results

📁 Theory & Notes
  📝 Pendulum Theory
  📝 Simulation Methodology
```

## Data Columns

Each simulation dataset includes:
- **Time**: Simulation time (seconds)
- **Angle_rad**: Angular position (radians)
- **Angle_deg**: Angular position (degrees)
- **Angular_Velocity**: Angular velocity (rad/s)
- **Position_X/Y**: Cartesian coordinates (meters)
- **Velocity_X/Y**: Cartesian velocities (m/s)
- **Kinetic_Energy**: Kinetic energy (Joules)
- **Potential_Energy**: Potential energy (Joules)
- **Total_Energy**: Total mechanical energy (Joules)

## Physics Concepts Demonstrated

1. **Damped Oscillations**: How friction affects pendulum motion
2. **Energy Dissipation**: Gradual loss of mechanical energy
3. **Phase Space**: Relationship between position and velocity
4. **Numerical Integration**: RK4 method for solving differential equations
5. **Parameter Studies**: Effect of varying damping coefficients

## Educational Applications

This example is perfect for:
- **Physics Education**: Demonstrating oscillatory motion and damping
- **Data Analysis**: Working with time series and parameter studies
- **Visualization**: Creating meaningful scientific plots
- **Project Organization**: Managing complex simulation projects

## Customization

You can modify the simulation by changing parameters in `create_pendulum_simulation.py`:
- `length`: Pendulum length (meters)
- `damping`: Damping coefficient
- `initial_angle`: Starting angle (radians)
- `time_duration`: Simulation time (seconds)
- `time_step`: Integration step size (seconds)

## Requirements

The simulation uses standard scientific Python libraries:
- NumPy: Numerical computations
- Pandas: Data management
- Matplotlib: Visualization (for demo)
- SciPy: Not required but available

All dependencies are listed in the main `requirements.txt` file.

## Advanced Features

The example demonstrates several advanced concepts:
- **4th-order Runge-Kutta integration** for accurate solutions
- **Parameter sweeps** for comparative analysis
- **Energy analysis** for system validation
- **Phase portrait analysis** for dynamic behavior
- **Comprehensive documentation** with theory and methodology

This example serves as a template for creating other physics simulations and scientific data analysis projects.
