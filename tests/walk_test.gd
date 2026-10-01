extends SceneTree
## Headless 測試：散步模式——高度跟著地形、露營車擋得住、走進池塘會涉水而不是潛下去。
## Godot --headless --path . --script res://tests/walk_test.gd

var main: Node3D
var frame := 0


func _initialize() -> void:
	main = (load("res://forest.tscn") as PackedScene).instantiate()
	root.add_child(main)


func _put(p: Vector2) -> void:
	main.walker.position = Vector3(p.x, main.h(p.x, p.y), p.y)
	main.walker.velocity = Vector3.ZERO


func _physics_process(_d: float) -> bool:
	frame += 1
	match frame:
		5:
			main._enter_walk()
			main.yaw = 0.0                      # yaw 0：輸入 (-1, 0) 就是往 -x 走
			_put(main.VAN + Vector2(4.0, 0.0))   # 車子 +x 側 4 m，朝車走
			main.walker.auto_input = Vector2(-1, 0)
		125:
			var p: Vector3 = main.walker.position
			print("WALK van: dist to van center=%.2f (unblocked would be ~0)  y-h=%.3f  speed=%.2f" % [
				Vector2(p.x, p.z).distance_to(main.VAN), p.y - main.h(p.x, p.z), main.walker.speed])
			_put(main.POND + Vector2(-7.0, 0.0))  # 池塘西側 7 m，往 +x 走進水裡
			main.walker.auto_input = Vector2(1, 0)
		245:
			var p: Vector3 = main.walker.position
			print("WALK pond: x-POND.x=%.2f  y=%.2f  terrain=%.2f  water=%.2f  gait=%.2f" % [
				p.x - main.POND.x, p.y, main.h(p.x, p.z), main.WATER_Y, main.walker.gait])
			main.walker.auto_input = Vector2.ZERO
		300:
			print("WALK stop: speed=%.2f gait=%.2f" % [main.walker.speed, main.walker.gait])
			main.toggle_walk()
			print("WALK exit: walk_mode=%s dist=%.0f" % [main.walk_mode, main.dist])
			quit()
	return false
