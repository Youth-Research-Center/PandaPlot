"""
Example script creating a damped pendulum simulation project.
This example demonstrates mathematical modeling and physics visualization.
"""

import pandas as pd
import numpy as np
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pandaplot.models.project import Project
from pandaplot.models.project.items import Folder, Dataset, Chart, Note
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager


def simulate_damped_pendulum(length=1.0, gravity=9.81, damping=0.1, 
                           initial_angle=np.pi/4, initial_velocity=0.0,
                           time_duration=20.0, time_step=0.01):
    """
    Simulate a damped pendulum using numerical integration.
    
    Args:
        length: Length of pendulum (m)
        gravity: Gravitational acceleration (m/s²)
        damping: Damping coefficient
        initial_angle: Initial angle (rad)
        initial_velocity: Initial angular velocity (rad/s)
        time_duration: Simulation time (s)
        time_step: Time step for integration (s)
    
    Returns:
        DataFrame with time, angle, velocity, and energy data
    """
    # Time array
    t = np.arange(0, time_duration, time_step)
    n_steps = len(t)
    
    # Initialize arrays
    theta = np.zeros(n_steps)
    omega = np.zeros(n_steps)
    
    # Set initial conditions
    theta[0] = initial_angle
    omega[0] = initial_velocity
    
    # Simulation parameters
    g_over_l = gravity / length
    
    # Numerical integration using Runge-Kutta 4th order
    for i in range(n_steps - 1):
        dt = time_step
        
        # Current state
        th = theta[i]
        om = omega[i]
        
        # RK4 integration
        k1_th = om
        k1_om = -g_over_l * np.sin(th) - damping * om
        
        k2_th = om + 0.5 * dt * k1_om
        k2_om = -g_over_l * np.sin(th + 0.5 * dt * k1_th) - damping * (om + 0.5 * dt * k1_om)
        
        k3_th = om + 0.5 * dt * k2_om
        k3_om = -g_over_l * np.sin(th + 0.5 * dt * k2_th) - damping * (om + 0.5 * dt * k2_om)
        
        k4_th = om + dt * k3_om
        k4_om = -g_over_l * np.sin(th + dt * k3_th) - damping * (om + dt * k3_om)
        
        # Update state
        theta[i + 1] = th + (dt / 6) * (k1_th + 2*k2_th + 2*k3_th + k4_th)
        omega[i + 1] = om + (dt / 6) * (k1_om + 2*k2_om + 2*k3_om + k4_om)
    
    # Calculate additional quantities
    position_x = length * np.sin(theta)
    position_y = -length * np.cos(theta)
    velocity_x = length * omega * np.cos(theta)
    velocity_y = length * omega * np.sin(theta)
    
    # Energy calculations
    kinetic_energy = 0.5 * length**2 * omega**2
    potential_energy = length * gravity * (1 - np.cos(theta))
    total_energy = kinetic_energy + potential_energy
    
    # Create DataFrame
    data = pd.DataFrame({
        'Time': t,
        'Angle_rad': theta,
        'Angle_deg': np.degrees(theta),
        'Angular_Velocity': omega,
        'Position_X': position_x,
        'Position_Y': position_y,
        'Velocity_X': velocity_x,
        'Velocity_Y': velocity_y,
        'Kinetic_Energy': kinetic_energy,
        'Potential_Energy': potential_energy,
        'Total_Energy': total_energy
    })
    
    return data


def create_parameter_study():
    """Create datasets for different damping coefficients."""
    damping_values = [0.0, 0.05, 0.1, 0.2, 0.5]
    results = {}
    
    for damping in damping_values:
        data = simulate_damped_pendulum(damping=damping, time_duration=15.0)
        results[f"damping_{damping:.2f}"] = data
    
    return results


def create_project_data_manager() -> ProjectDataManager:
    """Create and configure the project data manager."""
    item_data_manager_factory = ItemDataManagerFactory()

    item_data_manager_factory.register(
        type_name="note",
        item_class=Note,
        manager=NoteDataManager(),
        extension="note"
    )

    item_data_manager_factory.register(
        type_name="folder",
        item_class=Folder,
        manager=FolderDataManager(),
        extension="folder"
    )

    item_data_manager_factory.register(
        type_name="chart",
        item_class=Chart,
        manager=ChartDataManager(),
        extension="chart"
    )

    item_data_manager_factory.register(
        type_name="dataset",
        item_class=Dataset,
        manager=DatasetDataManager(),
        extension="dataset"
    )

    project_data_manager = ProjectDataManager(item_data_manager_factory)
    return project_data_manager


def create_pendulum_project():
    """Create a comprehensive pendulum simulation project."""
    
    # Create project and data manager
    project = Project(name="Damped Pendulum Simulation", description="Mathematical modeling and physics visualization")
    project_data_manager = create_project_data_manager()
    
    # Create folder structure
    simulations_folder = Folder(name="Simulations")
    analysis_folder = Folder(name="Analysis")
    theory_folder = Folder(name="Theory & Notes")
    parameter_study_folder = Folder(name="Parameter Study")
    
    # Add folders to project
    project.add_item(simulations_folder)
    project.add_item(analysis_folder)
    project.add_item(theory_folder)
    project.add_item(parameter_study_folder, simulations_folder.id)
    
    # Create main simulation dataset
    print("Generating main pendulum simulation...")
    main_data = simulate_damped_pendulum(
        length=1.0, 
        damping=0.1, 
        initial_angle=np.pi/3,  # 60 degrees
        time_duration=20.0
    )
    
    main_dataset = Dataset(name="Main Simulation (γ=0.1)", data=main_data)
    project.add_item(main_dataset, simulations_folder.id)
    
    # Create parameter study datasets
    print("Generating parameter study...")
    param_studies = create_parameter_study()
    
    for name, data in param_studies.items():
        damping_val = name.split('_')[1]
        dataset_name = f"Damping γ={damping_val}"
        dataset = Dataset(name=dataset_name, data=data)
        project.add_item(dataset, parameter_study_folder.id)
    
    # Create comparison dataset for envelope analysis
    print("Creating envelope analysis...")
    envelope_data = create_envelope_analysis()
    envelope_dataset = Dataset(name="Amplitude Envelope", data=envelope_data)
    project.add_item(envelope_dataset, analysis_folder.id)
    
    # Create charts
    print("Creating charts...")
    
    # 1. Main pendulum motion
    angle_chart = Chart(name="Pendulum Angle vs Time (Damping γ=0.1)", chart_type="line")
    angle_chart.config.update({
        'title': 'Pendulum Angle vs Time (Damping γ=0.1)',
        'x_label': 'Time (s)',
        'y_label': 'Angle (degrees)'
    })
    # Create data series for the chart
    from pandaplot.models.project.items.chart import DataSeries
    angle_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Time',
        y_column='Angle_deg',
        label='Angle',
        color='#1f77b4'
    )
    angle_chart.data_series.append(angle_series)
    project.add_item(angle_chart, analysis_folder.id)
    
    # 2. Phase portrait
    phase_chart = Chart(name="Phase Portrait (θ vs ω)", chart_type="scatter")
    phase_chart.config.update({
        'title': 'Phase Portrait (θ vs ω)',
        'x_label': 'Angle (rad)',
        'y_label': 'Angular Velocity (rad/s)'
    })
    phase_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Angle_rad',
        y_column='Angular_Velocity',
        label='Phase Space',
        color='#ff7f0e'
    )
    phase_chart.data_series.append(phase_series)
    project.add_item(phase_chart, analysis_folder.id)
    
    # 3. Energy analysis
    energy_chart = Chart(name="Energy Analysis", chart_type="line")
    energy_chart.config.update({
        'title': 'Energy vs Time',
        'x_label': 'Time (s)',
        'y_label': 'Energy (J)'
    })
    energy_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Time',
        y_column='Total_Energy',
        label='Total Energy',
        color="#2c5ea0"
    )

    kinetic_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Time',
        y_column='Kinetic_Energy',
        label='Kinetic Energy',
        color='#2ca02c'
    )

    potential_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Time',
        y_column='Potential_Energy',
        label='Potential Energy',
        color="#a07d2c"
    )

    energy_chart.data_series.append(energy_series)
    energy_chart.data_series.append(kinetic_series)
    energy_chart.data_series.append(potential_series)
    project.add_item(energy_chart, analysis_folder.id)
    
    # 4. Pendulum trajectory
    trajectory_chart = Chart(name="Pendulum Trajectory", chart_type="scatter")
    trajectory_chart.config.update({
        'title': 'Pendulum Trajectory',
        'x_label': 'X Position (m)',
        'y_label': 'Y Position (m)'
    })
    trajectory_series = DataSeries(
        dataset_id=main_dataset.id,
        x_column='Position_X',
        y_column='Position_Y',
        label='Trajectory',
        color='#d62728'
    )
    trajectory_chart.data_series.append(trajectory_series)
    project.add_item(trajectory_chart, analysis_folder.id)
    
    # Create theoretical notes
    create_theory_notes(project, theory_folder.id)
    
    # Create analysis summary
    create_analysis_summary(project, analysis_folder.id, main_data)
    
    # Save the project
    project_file = os.path.join(os.path.dirname(__file__), "pendulum_simulation.pplot")
    project_data_manager.save(project, project_file)
    
    print(f"\nPendulum simulation project created and saved to: {project_file}")
    print("\nProject structure:")
    print_project_structure(project, project.root.id, 0)
    
    return project


def create_envelope_analysis():
    """Create envelope analysis for amplitude decay."""
    time_points = np.linspace(0, 20, 100)
    damping_values = [0.05, 0.1, 0.2, 0.5]
    
    data = {'Time': time_points}
    
    for damping in damping_values:
        # Theoretical envelope for small angle approximation
        omega_0 = np.sqrt(9.81)  # Natural frequency
        
        initial_amplitude = np.pi/3  # 60 degrees initial
        envelope = initial_amplitude * np.exp(-damping * omega_0 * time_points)
        
        data[f'Envelope_γ{damping:.2f}'] = envelope
    
    return pd.DataFrame(data)


def create_theory_notes(project, theory_folder_id):
    """Create theoretical background notes."""
    
    # Main theory note
    theory_note = Note(name="Pendulum Theory")
    theory_content = """# Damped Pendulum Theory

## Equation of Motion
The equation of motion for a damped pendulum is:

**θ̈ + 2γθ̇ + ω₀²sin(θ) = 0**

Where:
- θ: Angular displacement from vertical
- γ: Damping coefficient  
- ω₀ = √(g/L): Natural frequency
- g: Gravitational acceleration
- L: Pendulum length

## Small Angle Approximation
For small angles (θ < 15°), sin(θ) ≈ θ, giving:

**θ̈ + 2γθ̇ + ω₀²θ = 0**

## Solution Types

### 1. Underdamped (γ < ω₀)
- Oscillatory motion with exponentially decaying amplitude
- Solution: θ(t) = Ae^(-γt)cos(ω_d t + φ)
- Damped frequency: ω_d = ω₀√(1 - γ²/ω₀²)

### 2. Critically Damped (γ = ω₀)
- Fastest return to equilibrium without oscillation
- Solution: θ(t) = (A + Bt)e^(-γt)

### 3. Overdamped (γ > ω₀)
- Slow return to equilibrium without oscillation
- Solution: θ(t) = Ae^(r₁t) + Be^(r₂t)

## Energy Considerations
In a damped system, mechanical energy is not conserved:
- Total energy decreases exponentially
- Rate of energy loss proportional to velocity squared
- Power dissipation: P = -γLω²
"""
    theory_note.content = theory_content
    project.add_item(theory_note, theory_folder_id)
    
    # Simulation methodology note
    method_note = Note(name="Simulation Methodology")
    method_content = """# Simulation Methodology

## Numerical Integration
This simulation uses the 4th-order Runge-Kutta (RK4) method for solving the differential equation.

### Why RK4?
- Higher accuracy than Euler's method
- Good stability properties
- Suitable for oscillatory systems
- Preserves energy better than simpler methods

## Implementation Details

### State Variables
- θ: Angular position (rad)
- ω: Angular velocity (rad/s)

### Differential Equations
- dθ/dt = ω
- dω/dt = -(g/L)sin(θ) - γω

### Parameters Used
- Length (L): 1.0 m
- Gravity (g): 9.81 m/s²
- Time step (dt): 0.01 s
- Initial angle: π/3 rad (60°)
- Initial velocity: 0 rad/s

## Validation
The simulation can be validated by:
1. Energy conservation (for γ=0)
2. Period comparison with analytical solution
3. Amplitude decay rate matching theory
"""
    method_note.content = method_content
    project.add_item(method_note, theory_folder_id)


def create_analysis_summary(project, analysis_folder_id, main_data):
    """Create analysis summary with actual results."""
    
    # Calculate some statistics
    max_angle = np.max(np.abs(main_data['Angle_rad']))
    min_angle = np.min(main_data['Angle_rad'])
    period_estimate = estimate_period(main_data)
    energy_loss = (main_data['Total_Energy'].iloc[0] - main_data['Total_Energy'].iloc[-1]) / main_data['Total_Energy'].iloc[0] * 100
    
    summary_note = Note(name="Simulation Results")
    summary_content = f"""# Damped Pendulum Simulation Results

## Simulation Parameters
- Initial angle: 60° ({np.pi/3:.3f} rad)
- Pendulum length: 1.0 m
- Damping coefficient: 0.1
- Simulation time: 20 s

## Key Results

### Motion Characteristics
- Maximum angle reached: {np.degrees(max_angle):.2f}°
- Minimum angle reached: {np.degrees(min_angle):.2f}°
- Estimated period: {period_estimate:.2f} s
- Theoretical period (undamped): {2*np.pi/np.sqrt(9.81):.2f} s

### Energy Analysis
- Initial energy: {main_data['Total_Energy'].iloc[0]:.3f} J
- Final energy: {main_data['Total_Energy'].iloc[-1]:.3f} J
- Energy loss: {energy_loss:.1f}%

### Damping Effects
The damping coefficient γ=0.1 results in:
- Underdamped oscillation
- Exponential decay of amplitude
- Gradual energy dissipation
- Period slightly longer than undamped case

## Observations
1. **Phase Portrait**: Shows spiral convergence to origin
2. **Energy Decay**: Monotonic decrease as expected
3. **Amplitude Decay**: Follows exponential envelope
4. **Period**: Slightly increased due to damping

## Applications
This simulation model applies to:
- Clock pendulums
- Seismic motion analysis
- Vibration damping systems
- Educational demonstrations
"""
    summary_note.content = summary_content
    project.add_item(summary_note, analysis_folder_id)


def estimate_period(data):
    """Estimate the period from zero crossings."""
    angles = data['Angle_rad'].values
    time = data['Time'].values
    
    # Find zero crossings
    zero_crossings = []
    for i in range(len(angles) - 1):
        if angles[i] * angles[i + 1] < 0:  # Sign change
            # Linear interpolation to find exact crossing
            t_cross = time[i] - angles[i] * (time[i + 1] - time[i]) / (angles[i + 1] - angles[i])
            zero_crossings.append(t_cross)
    
    if len(zero_crossings) >= 2:
        # Period is twice the time between consecutive crossings
        periods = []
        for i in range(len(zero_crossings) - 1):
            periods.append(2 * (zero_crossings[i + 1] - zero_crossings[i]))
        return np.mean(periods)
    else:
        return 2 * np.pi / np.sqrt(9.81)  # Theoretical fallback


def print_project_structure(project, item_id, indent_level):
    """Print the project structure in a tree format."""
    if item_id == project.root.id:
        # For root, print its children
        print(f"📁 {project.name}")
        for child in project.root.get_items():
            print_project_structure(project, child.id, indent_level + 1)
    else:
        # Find the item
        item = project.find_item(item_id)
        if not item:
            return
        
        indent = "  " * indent_level
        # Determine item type icon based on the class type
        if hasattr(item, '__class__'):
            class_name = item.__class__.__name__.lower()
            icon = {"folder": "📁", "dataset": "📊", "chart": "📈", "note": "📝"}.get(class_name, "📄")
        else:
            icon = "📄"
        
        print(f"{indent}{icon} {item.name}")
        
        # If it's a folder/collection, print its children
        if hasattr(item, 'get_items'):
            for child in item.get_items():
                print_project_structure(project, child.id, indent_level + 1)


if __name__ == "__main__":
    print("Creating damped pendulum simulation project...")
    print("This may take a moment to generate all the simulation data...")
    create_pendulum_project()
    print("\nProject creation complete!")
    print("\nTo use this project:")
    print("1. Open the plotter application")
    print("2. Load the 'pendulum_simulation.pplot' file")
    print("3. Explore the datasets, charts, and theory notes")
