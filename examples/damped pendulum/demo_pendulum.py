"""
Simple demonstration of the damped pendulum simulation.
Run this to create the project file and see basic results.
"""

import matplotlib.pyplot as plt
import sys
import os

# Add examples directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from create_pendulum_simulation import simulate_damped_pendulum, create_pendulum_project


def demo_pendulum():
    """Quick demonstration of pendulum simulation."""
    
    print("Damped Pendulum Simulation Demo")
    print("=" * 40)
    
    # Create a quick simulation
    print("\n1. Running simulation...")
    data = simulate_damped_pendulum(
        length=1.0,
        damping=0.1,
        initial_angle=60 * 3.14159/180,  # 60 degrees in radians
        time_duration=15.0
    )
    
    print(f"   - Simulated {len(data)} time points")
    print(f"   - Time range: 0 to {data['Time'].max():.1f} seconds")
    print(f"   - Initial angle: {data['Angle_deg'].iloc[0]:.1f} degrees")
    print(f"   - Final angle: {data['Angle_deg'].iloc[-1]:.1f} degrees")
    
    # Create and show a simple plot
    print("\n2. Creating basic visualization...")
    plt.figure(figsize=(12, 8))
    
    # Plot 1: Angle vs time
    plt.subplot(2, 2, 1)
    plt.plot(data['Time'], data['Angle_deg'])
    plt.title('Pendulum Angle vs Time')
    plt.xlabel('Time (s)')
    plt.ylabel('Angle (degrees)')
    plt.grid(True)
    
    # Plot 2: Phase portrait
    plt.subplot(2, 2, 2)
    plt.plot(data['Angle_rad'], data['Angular_Velocity'])
    plt.title('Phase Portrait')
    plt.xlabel('Angle (rad)')
    plt.ylabel('Angular Velocity (rad/s)')
    plt.grid(True)
    
    # Plot 3: Energy
    plt.subplot(2, 2, 3)
    plt.plot(data['Time'], data['Total_Energy'], label='Total')
    plt.plot(data['Time'], data['Kinetic_Energy'], label='Kinetic')
    plt.plot(data['Time'], data['Potential_Energy'], label='Potential')
    plt.title('Energy vs Time')
    plt.xlabel('Time (s)')
    plt.ylabel('Energy (J)')
    plt.legend()
    plt.grid(True)
    
    # Plot 4: Trajectory
    plt.subplot(2, 2, 4)
    plt.plot(data['Position_X'], data['Position_Y'])
    plt.title('Pendulum Trajectory')
    plt.xlabel('X Position (m)')
    plt.ylabel('Y Position (m)')
    plt.axis('equal')
    plt.grid(True)
    
    plt.tight_layout()
    
    # Save the plot
    plot_file = os.path.join(os.path.dirname(__file__), "pendulum_demo.png")
    plt.savefig(plot_file, dpi=150, bbox_inches='tight')
    print(f"   - Saved demo plot to: {plot_file}")
    
    # Show plot if possible
    try:
        plt.show()
    except Exception:
        print("   - Cannot display plot in this environment")
    
    # Create the full project
    print("\n3. Creating full project file...")
    create_pendulum_project()
    
    print("\n" + "=" * 40)
    print("Demo complete!")
    print("\nWhat was created:")
    print("- pendulum_simulation.pplot: Full project file for the plotter app")
    print("- pendulum_demo.png: Quick visualization of the simulation")
    print("\nTo explore further:")
    print("- Open pendulum_simulation.pplot in the plotter application")
    print("- Examine the different datasets for various damping coefficients")
    print("- Read the theory notes for mathematical background")
    print("- Analyze the charts for different aspects of pendulum motion")


if __name__ == "__main__":
    demo_pendulum()
