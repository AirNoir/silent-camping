extends SceneTree
## Headless 測試：採蘑菇小任務——接任務會生出 5 朵帶記號的蘑菇、逐一採完、回報交差後營火變旺。
## Godot --headless --path . --script res://tests/quest_test.gd

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
			_put(main.roaster_pos + Vector2(0.8, 0.0))
			main._interact()
			print("QUEST start: quest=%d items=%d need=%d" % [main.quest, main.quest_items.size(), main.quest_need])
		10:
			while main.quest_items.size() > 0:
				var p: Vector3 = main.quest_items[0]["pos"]
				_put(Vector2(p.x, p.z))
				main._interact()
			print("QUEST picked: got=%d/%d" % [main.quest_got, main.quest_need])
		15:
			_put(main.roaster_pos + Vector2(0.8, 0.0))
			main._interact()
			print("QUEST done: quest=%d celebrate=%.1f fire_boost=%.1f" % [main.quest, main.celebrate_t, main.fire_boost])
			quit()
	return false
