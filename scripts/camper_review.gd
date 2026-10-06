extends Node3D
## Standalone visual review. Run this scene with F6, keeping the main game intact.

var camera: Camera3D
var yaw := 0.45
var pitch := 0.10
var distance := 3.5
var dragging := false
var rotating := false
var model: Node3D

func _ready() -> void:
	model = (load("res://assets/gen/camper_male_sculpt.glb") as PackedScene).instantiate()
	add_child(model)
	if "--asset-check" in OS.get_cmdline_user_args():
		var meshes := model.find_children("*", "MeshInstance3D", true, false)
		var triangle_count := 0
		var bounds := AABB()
		for item in meshes:
			var instance := item as MeshInstance3D
			assert(instance.mesh != null)
			var box := instance.global_transform * instance.get_aabb()
			bounds = box if bounds.size == Vector3.ZERO else bounds.merge(box)
			for surface in instance.mesh.get_surface_count():
				assert(instance.mesh.surface_get_material(surface) != null)
				var arrays := instance.mesh.surface_get_arrays(surface)
				triangle_count += arrays[Mesh.ARRAY_INDEX].size() / 3
		assert(bounds.size.y > 1.2 and bounds.size.y < 1.5)
		assert(bounds.position.y >= -0.01)
		assert(meshes.size() > 0 and meshes.size() < 40)
		print("CAMPER_IMPORT_OK meshes=", meshes.size(), " triangles=", triangle_count, " bounds=", bounds)
		get_tree().quit()
		return
	var environment := WorldEnvironment.new()
	var settings := Environment.new()
	settings.background_mode = Environment.BG_COLOR
	settings.background_color = Color("e5e1d9")
	settings.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	settings.ambient_light_color = Color("e5e5e5")
	settings.ambient_light_energy = 0.7
	settings.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	environment.environment = settings
	add_child(environment)
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-42, -35, 0)
	light.light_energy = 1.0
	light.light_color = Color("ffe9cf")
	light.shadow_enabled = true
	add_child(light)
	var floor_mesh := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(200, 200)
	var floor_material := StandardMaterial3D.new()
	floor_material.albedo_color = Color("e5e1d9")
	floor_material.roughness = 0.9
	plane.material = floor_material
	floor_mesh.mesh = plane
	add_child(floor_mesh)
	camera = Camera3D.new()
	camera.projection = Camera3D.PROJECTION_ORTHOGONAL
	camera.size = 1.65
	camera.current = true
	add_child(camera)
	var canvas := CanvasLayer.new()
	var label := Label.new()
	label.text = "Male camper · Drag to rotate · Scroll to zoom · 1/2/3/4 views · Space auto rotate"
	label.position = Vector2(16, 16)
	label.add_theme_color_override("font_color", Color("493d34"))
	canvas.add_child(label)
	add_child(canvas)
	_update_camera()

func _process(delta: float) -> void:
	if camera == null:
		return
	if rotating:
		yaw += delta * 0.3
	_update_camera()

func _update_camera() -> void:
	var center := Vector3(0, 0.68, 0)
	camera.position = center + Vector3(cos(yaw) * cos(pitch), sin(pitch), sin(yaw) * cos(pitch)) * distance
	camera.look_at(center)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_LEFT:
			dragging = event.pressed
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_UP:
			camera.size = maxf(0.55, camera.size * 0.92)
		if event.pressed and event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			camera.size = minf(3.0, camera.size * 1.08)
	elif event is InputEventMouseMotion and dragging:
		yaw -= event.relative.x * 0.008
		pitch = clampf(pitch + event.relative.y * 0.006, -0.3, 0.7)
	elif event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_1: yaw = 0.0; pitch = 0.0
			KEY_2: yaw = 0.5; pitch = 0.1
			KEY_3: yaw = PI / 2.0; pitch = 0.0
			KEY_4: yaw = PI; pitch = 0.0
			KEY_SPACE: rotating = not rotating
