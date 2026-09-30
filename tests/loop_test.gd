extends SceneTree
## Headless test for the full game loop: push the rock onto the plate, collect all gears, repair the windmill.
## Godot --headless --path . --script res://tests/loop_test.gd

var main: Node3D
var frame := 0
var rock_z0 := 0.0

func _initialize() -> void:
	main = (load("res://main.tscn") as PackedScene).instantiate()
	root.add_child(main)

func _physics_process(_d: float) -> bool:
	frame += 1
	var p = main.player
	match frame:
		30:
			# stand behind the rock (uphill side, -z) and hold forward toward +z
			var r: Vector3 = main.rock_start
			rock_z0 = main.rock.global_position.z
			p.global_position = Vector3(r.x, r.y - 0.9, r.z - 2.6)
			p.velocity = Vector3.ZERO
			p.pivot.rotation = Vector3(-0.3, PI, 0)  # camera behind player looking toward +z
			Input.action_press("move_forward")
		120:
			print("ROCK after 90 frames of pushing: moved %.1f m in z, y=%.1f" % [main.rock.global_position.z - rock_z0, main.rock.global_position.y])
		400:
			Input.action_release("move_forward")
			print("ROCK final pos=%s  plate_done=%s  gears in world=%d" % [main.rock.global_position.round(), main.plate_done, main.gears.size()])
		420:
			# collect every gear by teleporting into it
			var positions: Array[Vector3] = []
			for g: Area3D in main.gears:
				positions.append(g.global_position)
			for i in positions.size():
				var pos: Vector3 = positions[i]
				get_tree_timer(i, pos)
		620:
			print("GEARS found=%d / %d" % [main.gears_found, main.GEARS_TOTAL])
			p.global_position = main.WINDMILL + Vector3(4, 0.5, 0)
			p.velocity = Vector3.ZERO
		660:
			print("REPAIRED=%s  hint='%s'" % [main.repaired, main.hint_label.text.replace("\n", " / ")])
			return true
	return false

func get_tree_timer(i: int, pos: Vector3) -> void:
	# stagger the teleports so each Area3D overlap registers on its own frame
	var t := create_timer(0.3 * i + 0.05)
	t.timeout.connect(func() -> void:
		main.player.global_position = pos
		main.player.velocity = Vector3.ZERO)
