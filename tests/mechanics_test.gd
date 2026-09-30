extends SceneTree
## Headless smoke test for bounce / climb / glide. Run:
## Godot --headless --path . --script res://tests/mechanics_test.gd

var main: Node3D
var frame := 0
var log_max := 0.0

func _initialize() -> void:
	main = (load("res://main.tscn") as PackedScene).instantiate()
	root.add_child(main)

func _physics_process(_d: float) -> bool:
	frame += 1
	var p = main.player
	match frame:
		30:  # drop onto the mushroom
			p.global_position = Vector3(main.MUSHROOM.x, main.h(main.MUSHROOM.x, main.MUSHROOM.y) + 5.0, main.MUSHROOM.y)
			p.velocity = Vector3.ZERO
			log_max = 0.0
		150:
			print("BOUNCE max height above mushroom base: %.1f m (platform at +14)" % (log_max - main.h(main.MUSHROOM.x, main.MUSHROOM.y)))
			# stand next to the pillar facing it and hold forward
			var base: float = main.h(main.PILLAR.x, main.PILLAR.y)
			p.global_position = Vector3(main.PILLAR.x + 3.6, base + 0.5, main.PILLAR.y)
			p.velocity = Vector3.ZERO
			p.pivot.rotation = Vector3(-0.3, PI / 2, 0)  # camera looks toward -X (the pillar)
			Input.action_press("move_forward")
			log_max = 0.0
		500:
			Input.action_release("move_forward")
			print("CLIMB reached %.1f m above ground (pillar top ~+16), climbing=%s stamina=%.0f" % [log_max - main.h(main.PILLAR.x, main.PILLAR.y), p.climbing, p.stamina])
			# glide from high up
			p.global_position = Vector3(main.GLIDE_HILL.x, 40.0, main.GLIDE_HILL.y)
			p.velocity = Vector3.ZERO
			p.climbing = false
		520:
			Input.action_press("jump")
		521:
			Input.action_release("jump")
		580:
			print("GLIDE gliding=%s vertical speed=%.1f (expect about -2.2)" % [p.gliding, p.velocity.y])
			return true
	log_max = maxf(log_max, p.global_position.y)
	return false
