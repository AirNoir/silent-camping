extends CharacterBody3D
## Chibi hero: walk / run / jump, BotW-style climbing (stamina), gliding and updrafts.

signal drowned

const SPEED := 6.0
const RUN_SPEED := 9.5
const JUMP_VELOCITY := 8.0
const GRAVITY := 20.0
const GLIDE_FALL := 2.2
const GLIDE_SPEED := 10.0
const CLIMB_SPEED := 3.2
const MAX_STAMINA := 100.0

var stamina := MAX_STAMINA
var exhausted := false
var gliding := false
var climbing := false
var updraft := 0.0
var water_level := -2.0
var safe_pos := Vector3.ZERO
var wall_normal := Vector3.ZERO
var climb_enabled := true

var pivot: Node3D
var model: Node3D
var glider: Node3D


func _ready() -> void:
	floor_max_angle = deg_to_rad(46.0)
	floor_snap_length = 0.4
	safe_pos = position
	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.4
	cap.height = 1.5
	col.shape = cap
	col.position.y = 0.75
	add_child(col)

	model = Node3D.new()
	add_child(model)
	_build_model()

	pivot = Node3D.new()
	pivot.position.y = 1.3
	pivot.rotation.x = -0.3
	add_child(pivot)
	var arm := SpringArm3D.new()
	arm.spring_length = 6.5
	arm.margin = 0.3
	arm.add_excluded_object(get_rid())
	pivot.add_child(arm)
	var cam := Camera3D.new()
	cam.current = true
	cam.fov = 70.0
	arm.add_child(cam)


func bounce(v: float) -> void:
	velocity.y = v
	gliding = false
	climbing = false


func _unhandled_input(event: InputEvent) -> void:
	var mm := event as InputEventMouseMotion
	if mm and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		pivot.rotation.y -= mm.relative.x * 0.004
		pivot.rotation.x = clampf(pivot.rotation.x - mm.relative.y * 0.004, -1.3, 0.6)
	elif event is InputEventMouseButton and event.is_pressed():
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE


func _physics_process(delta: float) -> void:
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	pivot.rotation.y -= Input.get_axis("cam_left", "cam_right") * 2.0 * delta
	var dir := Basis(Vector3.UP, pivot.rotation.y) * Vector3(input.x, 0.0, input.y)

	if is_on_floor():
		gliding = false
		if stamina >= MAX_STAMINA * 0.3:
			exhausted = false
		stamina = minf(MAX_STAMINA, stamina + 30.0 * delta)
		if global_position.y > water_level + 0.5:
			safe_pos = global_position

	if climb_enabled and not climbing and not exhausted and dir.length() > 0.1 and _static_wall_normal() != Vector3.ZERO:
		var n := _static_wall_normal()
		var flat_n := Vector3(n.x, 0.0, n.z).normalized()
		if n.y < 0.7 and n.y > -0.2 and dir.normalized().dot(-flat_n) > 0.5:
			climbing = true
			gliding = false

	if climbing:
		_climb(input, delta)
	elif gliding:
		_glide(dir, delta)
	else:
		_walk(dir, delta)

	glider.visible = gliding
	move_and_slide()
	_push_bodies()
	_update_model(delta)

	if global_position.y < water_level - 1.0:
		global_position = safe_pos + Vector3.UP
		velocity = Vector3.ZERO
		gliding = false
		climbing = false
		drowned.emit()


func _walk(dir: Vector3, delta: float) -> void:
	var running := Input.is_action_pressed("run") and not exhausted and dir.length() > 0.1 and is_on_floor()
	if running:
		stamina -= 12.0 * delta
		if stamina <= 0.0:
			stamina = 0.0
			exhausted = true
	var speed := RUN_SPEED if running else SPEED
	var accel := (12.0 if is_on_floor() else 4.0) * speed
	velocity.x = move_toward(velocity.x, dir.x * speed, accel * delta)
	velocity.z = move_toward(velocity.z, dir.z * speed, accel * delta)
	velocity.y -= GRAVITY * delta
	if Input.is_action_just_pressed("jump"):
		if is_on_floor():
			velocity.y = JUMP_VELOCITY
		elif not exhausted and stamina > 0.0:
			gliding = true


func _glide(dir: Vector3, delta: float) -> void:
	if Input.is_action_just_pressed("jump") or exhausted:
		gliding = false
		return
	stamina -= 3.0 * delta
	if stamina <= 0.0:
		stamina = 0.0
		exhausted = true
	var target := dir * GLIDE_SPEED if dir.length() > 0.1 else model.global_basis.z * 5.0
	velocity.x = move_toward(velocity.x, target.x, 10.0 * delta)
	velocity.z = move_toward(velocity.z, target.z, 10.0 * delta)
	velocity.y = move_toward(velocity.y, -GLIDE_FALL, 25.0 * delta)
	if updraft > 0.0:
		velocity.y = minf(velocity.y + updraft * delta, 9.0)


func _climb(input: Vector2, delta: float) -> void:
	if is_on_floor() and input.y >= 0.0:
		climbing = false
		return
	var n := _static_wall_normal()
	if n == Vector3.ZERO:
		# ran out of wall: hop over the ledge
		climbing = false
		velocity = Vector3.UP * 6.0 - wall_normal * 3.0
		return
	wall_normal = n
	if Input.is_action_just_pressed("jump"):
		climbing = false
		velocity = n * 5.0 + Vector3.UP * 5.0
		return
	var up := (Vector3.UP - n * n.dot(Vector3.UP)).normalized()
	var side := up.cross(n).normalized()
	var move := up * -input.y + side * input.x
	stamina -= (14.0 if move.length() > 0.1 else 4.0) * delta
	if stamina <= 0.0:
		stamina = 0.0
		exhausted = true
		climbing = false
		return
	velocity = move * CLIMB_SPEED - n * 1.5


func _static_wall_normal() -> Vector3:
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		if c.get_collider() is StaticBody3D and c.get_normal().y < 0.7:
			return c.get_normal()
	return Vector3.ZERO


func _push_bodies() -> void:
	for i in get_slide_collision_count():
		var c := get_slide_collision(i)
		var b := c.get_collider() as RigidBody3D
		if b:
			var push := -c.get_normal()
			push.y = 0.0
			if push.length() > 0.01:
				b.apply_central_impulse(push.normalized() * 0.6)


func _update_model(delta: float) -> void:
	var face := Vector3.ZERO
	var flat := Vector3(velocity.x, 0.0, velocity.z)
	if climbing:
		face = -wall_normal
	elif flat.length() > 0.5:
		face = flat
	if face.length() > 0.01:
		model.rotation.y = lerp_angle(model.rotation.y, atan2(face.x, face.z), 12.0 * delta)
	model.rotation.x = lerpf(model.rotation.x, 0.35 if gliding else 0.0, 6.0 * delta)


func _build_model() -> void:
	_part(_capsule(0.36, 1.0), Color(0.25, 0.62, 0.3), Vector3(0, 0.6, 0))
	_part(_sphere(0.4), Color(1.0, 0.85, 0.7), Vector3(0, 1.35, 0))
	var hat := _part(_cone(0.42, 0.8), Color(0.2, 0.55, 0.25), Vector3(0, 1.72, -0.12))
	hat.rotation.x = deg_to_rad(-25)
	for s in [-1.0, 1.0]:
		_part(_sphere(0.065), Color(0.08, 0.08, 0.08), Vector3(s * 0.14, 1.4, 0.35))
		_part(_sphere(0.07), Color(1.0, 0.6, 0.6), Vector3(s * 0.25, 1.27, 0.29))
		_part(_sphere(0.15), Color(0.45, 0.3, 0.15), Vector3(s * 0.16, 0.1, 0.05))
		_part(_sphere(0.12), Color(1.0, 0.85, 0.7), Vector3(s * 0.45, 0.75, 0.0))
	glider = Node3D.new()
	glider.position.y = 2.3
	glider.visible = false
	model.add_child(glider)
	var wing := BoxMesh.new()
	wing.size = Vector3(2.8, 0.08, 1.1)
	_part(wing, Color(0.95, 0.55, 0.2), Vector3.ZERO, glider)
	var stripe := BoxMesh.new()
	stripe.size = Vector3(2.82, 0.09, 0.3)
	_part(stripe, Color(0.85, 0.2, 0.2), Vector3.ZERO, glider)
	for s in [-1.0, 1.0]:
		var rod_mesh := CylinderMesh.new()
		rod_mesh.top_radius = 0.03
		rod_mesh.bottom_radius = 0.03
		rod_mesh.height = 1.6
		rod_mesh.radial_segments = 6
		var rod := _part(rod_mesh, Color(0.4, 0.25, 0.1), Vector3(s * 0.8, -0.8, 0), glider)
		rod.rotation.z = s * 0.35


func _part(mesh: Mesh, color: Color, pos: Vector3, parent: Node3D = null) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = preload("res://scripts/main.gd").flat_mesh(mesh)
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	m.roughness = 0.6
	mi.material_override = m
	mi.position = pos
	(parent if parent else model).add_child(mi)
	return mi


func _sphere(r: float) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = r
	m.height = r * 2.0
	m.radial_segments = 12
	m.rings = 6
	return m


func _capsule(r: float, hgt: float) -> CapsuleMesh:
	var m := CapsuleMesh.new()
	m.radius = r
	m.height = hgt
	m.radial_segments = 10
	m.rings = 2
	return m


func _cone(r: float, hgt: float) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = 0.0
	m.bottom_radius = r
	m.height = hgt
	m.radial_segments = 8
	return m
