# maps

**Saved SLAM Maps (Cartographer)**

## Purpose
Contains `.yaml` configuration files and map metadata for saved 2D SLAM maps. Each map represents a scanned environment that the robot can navigate in autonomously.

## Files

- **`test.yaml`**: Example/test map (minimal)
- Additional maps created at runtime by `hardware_service.py` endpoints

## Map File Format

Each saved map contains:
```
maps/
├── map_name/
│   ├── map.yaml          # YAML metadata
│   ├── map.pgm           # Occupancy grid (image format)
│   └── map.meta          # Cartographer serialized state
```

### Example map.yaml
```yaml
image: map.pgm
resolution: 0.05
origin: [-10.0, -10.0, 0.0]
negate: 0
occupied_thresh: 0.65
free_thresh: 0.196
```

| Field | Type | Meaning |
|-------|------|---------|
| `image` | str | Relative path to occupancy grid image |
| `resolution` | float | Grid cell size (meters; 0.05 = 5cm) |
| `origin` | [x, y, θ] | Map frame bottom-left corner, rotation |
| `negate` | 0/1 | Invert image colors (0 = white=free) |
| `occupied_thresh` | float | Pixel value > thresh = obstacle |
| `free_thresh` | float | Pixel value < thresh = free space |

## Creating & Managing Maps

### Save a New Map (during SLAM)
Run inside the `slam_mapping` tmux session:
```bash
ROS_DOMAIN_ID=28 ros2 run nav2_map_server map_saver_cli \
  -f /home/jetson/clawbot/maps/my_room \
  --ros-args -p map_subscribe_transient_local:=true
```

Output:
```
my_room.yaml
my_room.pgm
```

### Via Hardware Service API
```bash
curl -X POST http://localhost:8000/command \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "SaveMap",
    "map_name": "my_room"
  }'
```

### List Saved Maps
```bash
curl http://localhost:8000/command \
  -d '{"tool": "ListMaps"}'

# Returns:
# ["test", "my_room", "kitchen", ...]
```

### Load a Map (for Navigation)
```bash
curl -X POST http://localhost:8000/command \
  -d '{
    "tool": "LoadMap",
    "map_name": "my_room"
  }'

# Publishes to /map topic for Nav2 + Cartographer
```

### Get Map as Image
```bash
curl http://localhost:8000/maps/my_room/image > map.png
```

### Delete a Map
```bash
curl -X DELETE http://localhost:8000/maps/my_room
```

## Map Quality

- **Resolution**: 0.05 m/cell (5 cm grid)
  - Finer grid → more accurate but slower search
  - Coarser → faster but less precise
  
- **Coverage**: Depends on LiDAR range (~3.5 m) and environment size
  - Small rooms: ~5–10 minutes scan
  - Large rooms: 30+ minutes for complete coverage

- **Accuracy**: Cartographer 2D scan-matching with loop closure
  - Drift < 1–2% of total distance traveled
  - Loop closure reduces accumulated error

## Integration with Navigation

### RViz Visualization
```bash
# View saved map
ros2 run rviz2 rviz2 -d clawbot_default.rviz

# In RViz, add Map display → /map topic
# Select map from hardware_service dropdown
```

### Nav2 Autonomous Navigation
```bash
# Load map first
curl -X POST http://localhost:8000/command \
  -d '{"tool": "LoadMap", "map_name": "my_room"}'

# Then publish goal pose
ROS_DOMAIN_ID=28 ros2 topic pub /goal_pose geometry_msgs/PoseStamped \
  '{header: {frame_id: "map"}, 
    pose: {position: {x: 5.0, y: 5.0, z: 0.0}, 
           orientation: {w: 1.0}}}'
```

## File Layout

```
maps/
├── test.yaml           # Included in repo
├── test.pgm
├── my_room/
│   ├── my_room.yaml
│   ├── my_room.pgm
│   └── my_room.meta
├── kitchen/
│   ├── kitchen.yaml
│   ├── kitchen.pgm
│   └── kitchen.meta
└── README.md (this file)
```

## Storage Considerations

- **Disk Space**: Each map ≈ 500 KB – 5 MB (depends on area size)
- **Backup**: Recommend weekly backup of important maps
  ```bash
  tar czf maps_backup_$(date +%Y-%m-%d).tar.gz maps/
  ```

## Common Issues

### "Map not found" error
- Map name typo? Check `ListMaps` output
- Map saved in wrong directory? Verify `/home/jetson/clawbot/maps/`

### Map shows all black/white
- Occupancy threshold wrong (adjust `occupied_thresh` in YAML)
- LiDAR scan incomplete (re-scan environment)

### Map drifts over time
- Cartographer loop closure not triggered
- Try scanning in loop-shaped path (same start/end)
- Increase LiDAR scan frequency in `lds_2d.lua`

## Future Work

- [ ] 3D maps (Cartographer 3D)
- [ ] Multi-floor support (stacked 2D maps)
- [ ] Map merge (combine two adjacent scans)
- [ ] Cloud backup integration
- [ ] Version control for maps (Git LFS)

**Status**: ✅ Operational. Supports save/load/delete via API and CLI.

**Maintainer**: clawbot team
