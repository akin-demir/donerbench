Build an MVP web-based simulation environment called **DönerBench**.

## Concept

DönerBench is an AI-agent benchmark where multiple AI agents compete to produce the best döner slices within a 60-second simulated service window.

Each agent controls a virtual knife slicing a rotating döner cone. The system renders each agent’s run side-by-side, then compares their resulting slices using objective metrics.

## Core User Flow

1. User opens the web app.
2. User selects which AI models/agents should compete.
3. The screen splits automatically based on the number of selected agents:

   * 1 agent: full screen
   * 2 agents: vertical split
   * 3–4 agents: grid
4. Each panel shows:

   * rotating döner cone
   * knife movement
   * current slicing action
   * elapsed time
   * live score
5. Agents run for 60 simulated seconds.
6. At the end, show a comparison table ranking all agents.

## Simulation Inputs

Each agent may control these parameters per timestep:

* knife_angle
* knife_velocity
* inward_pressure
* vibration_frequency
* vibration_amplitude
* cut_location_from_top
* cut_depth
* timing_relative_to_rotation

Environment parameters:

* döner_rotation_speed
* heat_temperature
* cone_height
* cone_radius_top
* cone_radius_bottom
* meat_freshness_map
* cookedness_map
* surface_irregularity

## Outputs Per Slice

For every produced slice, calculate:

* thickness_mm
* thickness_variance
* surface_area_cm2
* volume_cm3
* freshness_score
* cookedness_score
* tear_penalty
* waste_penalty
* uniformity_score
* slice_score

## 60-Second Benchmark Score

Each agent’s final score should combine:

* average slice quality
* number of valid slices
* consistency across slices
* freshness
* low waste
* low tearing
* timing efficiency

Use this initial scoring formula:

final_score =
0.25 * average_slice_quality +
0.20 * uniformity_score +
0.15 * freshness_score +
0.15 * valid_slice_count_score +
0.10 * low_waste_score +
0.10 * low_tear_score +
0.05 * speed_score

Normalize all components to 0–100.

## Agent Interface

Create a simple agent API.

Each agent receives an observation:

{
time_remaining,
doner_rotation_angle,
doner_rotation_speed,
heat_temperature,
current_surface_geometry,
current_surface_freshness,
current_surface_cookedness,
knife_state,
previous_slice_metrics
}

Each agent returns an action:

{
knife_angle,
knife_velocity,
inward_pressure,
vibration_frequency,
vibration_amplitude,
cut_location_from_top,
cut_depth
}

For the MVP, include at least four built-in agents:

1. RandomAgent
2. ConservativeAgent
3. AggressiveAgent
4. BalancedAgent

The architecture should allow future LLM or RL agents to be plugged in.

## 3D Rendering

Use Three.js.

Render:

* rotating döner cone
* heat lamp or burner
* knife blade
* slice being removed
* surface marks after cutting
* optional floating score labels

The first version can use simplified geometry. The döner can be a cone/frustum mesh. Slices can be represented as thin curved rectangular mesh patches.

## UI Requirements

Main UI sections:

1. Agent selection panel
2. Benchmark configuration panel
3. Split-screen simulation viewer
4. Live metrics overlay per agent
5. Final leaderboard table
6. Slice comparison table

The final table should include:

* rank
* agent name
* final score
* number of valid slices
* average thickness
* thickness variance
* average area
* average freshness
* waste percentage
* tear penalty
* verdict

Example verdicts:

* Perfect service
* Excellent but slow
* Fast but wasteful
* Too thick
* Too aggressive
* Inconsistent slicing

## Technical Requirements

Use:

* TypeScript
* React
* Three.js
* Zustand or simple state management
* Vite

Structure the project cleanly:

src/
agents/
simulation/
scoring/
rendering/
components/
types/

Important files:

* Agent interface
* Simulation engine
* Scoring engine
* Three.js renderer
* Benchmark runner
* Leaderboard component

## MVP Priorities

Focus on making the benchmark understandable and visually compelling.

Do not over-engineer real meat physics yet.

Use simplified mathematical models for:

* slice thickness
* area
* freshness
* tearing
* waste
* uniformity

The simulator should be deterministic when given the same random seed.

## Deliverables

Produce:

1. Full project code.
2. Clear setup instructions.
3. Explanation of the simulation model.
4. Explanation of the scoring formula.
5. Notes on how to add new agents.
6. A working local demo.

## Design Tone

The app should feel like a serious AI benchmark with a playful subject.

Name: DönerBench
Subtitle: The Perfect Slice Benchmark
Main mode: 60-Second Service Challenge
