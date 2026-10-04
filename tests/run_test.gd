extends SceneTree
var main: Node3D
var frame := 0
func _initialize() -> void:
	main = (load("res://forest.tscn") as PackedScene).instantiate()
	root.add_child(main)
func _physics_process(_d: float) -> bool:
	frame += 1
	if frame == 5:
		main._enter_walk()
		main.yaw = 0.0
		main.walker.position = Vector3(5.0, main.h(5.0, 18.0), 18.0)
		main.walker.auto_input = Vector2(0, -1)   # yaw 0：往 -z 跑
		main.walker.auto_run = true
	elif frame > 5 and frame % 30 == 0:
		var p: Vector3 = main.walker.position
		print("RUN f=%d pos=(%.2f, %.2f) speed=%.2f gait=%.2f" % [frame, p.x, p.z, main.walker.speed, main.walker.gait])
	if frame >= 245:
		quit()
	return false
