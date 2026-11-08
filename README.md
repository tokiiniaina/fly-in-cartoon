*This project has been created as part of the 42 curriculum by <login>.*

# Fly-In

## Description

Fly-In routes a fleet of drones from a start zone to an end zone through a
network of zones and connections, in as few turns as possible. Zones have a
type (normal, priority, restricted, blocked) and a capacity; links have a
capacity too. The project contains:

- a map **parser** (`flyin/src/parser_function`),
- two **solvers** (`flyin/src/engine`) and an independent **output checker**,
- an isometric **game** with a menu, a map selection and an animated play
  screen (`flyin/src/viewer`).

## Instructions

```
make install        # Pillow + pygame-ce
make run            # opens the game menu
make run MAP=maps/easy/02_simple_fork.txt   # opens a map directly
python3 fly_in.py MAP --text                # prints the turns (subject format)
python3 fly_in.py MAP --png out.png         # final frame as an image
python3 fly_in.py MAP --gif out.gif         # animation as a GIF
make lint | make lint-strict | make clean | make debug
```

In play: `SPACE` pause, `<` `>` step, `R` restart, `UP/DOWN` speed,
`ESC` back. The best score of each map is kept in `.flyin_scores.json`.

Output format, one line per turn: `D1-roof1 D2-corridorA`; a drone that
starts a flight to a restricted zone prints the link (`D2-spring-bridge`)
and must land on the next turn.

## Algorithm choices

- **Space-time A\***: every drone is planned in (zone, turn) space against a
  reservation table of zones and links, so a later drone never breaks an
  earlier one. Distances come from a reverse Dijkstra.
- **Greedy simulator**: each turn, drones closer to the goal move first to
  the best free neighbour that is closer to the end.
- `solve()` runs both, validates each output with `OutputChecker`, and keeps
  the shortest valid one.
- Rules interpreted in `engine/rules.py`: a flight to a restricted zone
  holds its link for both turns, and a link capacity is shared by both
  directions.

## Visual

Pillow draws a supersampled isometric base (platforms, bridges, decor) once
per map, then composites the drones every frame; pygame is only the window
and event loop. Menus are Pillow sprites too.

## Resources

- Subject: 42 "Fly-in".
- Dijkstra and space-time A\* (cooperative pathfinding) literature.
- AI usage: Claude helped design and write the visual layer, the solver
  facade and the menus; the parser and the engines were written by the
  author, and all output is validated by `OutputChecker`.
