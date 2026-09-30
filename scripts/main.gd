extends Node3D
## 「風車齒輪」demo：程式生成山、湖、島，擺上 Kenney 素材，5 個齒輪謎題，修好營地的大風車。

const PlayerScript := preload("res://scripts/player.gd")

const N := 201
const HALF := 100.0
const WATER := -2.0
const NATURE := "res://assets/nature/"
const GEARS_TOTAL := 5

const MOUNTAIN := Vector2(50, -45)
const LAKE := Vector2(-45, 40)
const GLIDE_HILL := Vector2(-8, 60)
const PLATE_HILL := Vector2(38, 26)
const PLATE := Vector2(38, 39)
const PILLAR := Vector2(-28, 10)
const MUSHROOM := Vector2(17, 15)
const UPDRAFT := Vector2(-4, 33)
const WINDMILL := Vector3(-17, 0, -2)

const TREES := ["tree_default", "tree_oak", "tree_fat", "tree_detailed", "tree_tall", "tree_simple"]
const PINES := ["tree_pineTallA", "tree_pineTallB", "tree_pineRoundA", "tree_pineDefaultA", "tree_cone"]
const ROCKS := ["rock_largeA", "rock_largeB", "rock_largeC", "rock_largeD", "rock_tallA", "rock_tallB"]
const DECOR := ["flower_redA", "flower_yellowA", "flower_purpleA", "grass_large", "grass_leafs",
		"mushroom_red", "mushroom_tanGroup", "plant_bush", "plant_bushLarge"]

const WATER_SHADER := """
shader_type spatial;
render_mode blend_mix, cull_disabled, specular_schlick_ggx;
uniform vec4 tint : source_color = vec4(0.25, 0.65, 0.85, 0.78);
void vertex() {
	VERTEX.y += sin(VERTEX.x * 0.35 + TIME) * 0.06 + cos(VERTEX.z * 0.3 + TIME * 1.3) * 0.06;
}
void fragment() {
	float ripple = sin(UV.x * 400.0 + TIME * 1.5) * sin(UV.y * 400.0 - TIME);
	ALBEDO = tint.rgb + ripple * 0.03;
	ALPHA = tint.a;
	ROUGHNESS = 0.08;
	SPECULAR = 0.7;
}
"""

var noise := FastNoiseLite.new()
var rng := RandomNumberGenerator.new()
var player: PlayerScript
var gears: Array[Area3D] = []
var gears_found := 0
var repaired := false
var blades: Node3D
var rock: RigidBody3D
var rock_start := Vector3.ZERO
var plate_done := false
var plate_pos := Vector3.ZERO
var plate_mat: StandardMaterial3D
var tips: Array = []  # [position, radius, text]

var gear_label: Label
var hint_label: Label
var stamina_bar: ProgressBar
var stamina_fill: StyleBoxFlat
var hint_time := 0.0
var ding_stream: AudioStreamWAV


func _ready() -> void:
	rng.seed = 7
	noise.seed = 3
	noise.frequency = 0.015
	noise.fractal_octaves = 4
	ding_stream = _make_ding(1318.5)
	_setup_input()
	_setup_env()
	_build_terrain()
	_build_water()
	_build_bounds()
	_build_village()
	_build_windmill()
	_build_puzzles()
	_scatter_nature()
	_spawn_player()
	_build_hud()
	show_hint("目標：找到 5 個發光的風車齒輪，修好營地的大風車！\n爬到高處，找找遠方的金色光柱吧。", 7.0)
	for arg: String in OS.get_cmdline_user_args():
		if arg == "--overview":
			_debug_cam(Vector3(-20, 95, 125), Vector3(0, 0, 5))
		elif arg == "--place-rock":  # debug: show the solved switch
			_on_plate_body.call_deferred(rock, plate_pos)
		elif arg.begins_with("--cam="):
			var v := arg.trim_prefix("--cam=").split_floats(",")
			if v.size() == 6:
				_debug_cam(Vector3(v[0], v[1], v[2]), Vector3(v[3], v[4], v[5]))


func _debug_cam(pos: Vector3, target: Vector3) -> void:
	var cam := Camera3D.new()
	add_child(cam)
	cam.position = pos
	cam.look_at(target)
	cam.current = true


# ---------------------------------------------------------------- terrain

func h(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var lake_f := _g(p, LAKE, 16.0)
	var y := (noise.get_noise_2d(x, z) * 4.0 + noise.get_noise_2d(x * 0.25 + 300.0, z * 0.25) * 6.0) * (1.0 - lake_f)
	y += 34.0 * _g(p, MOUNTAIN, 16.0)
	y += 18.0 * _g(p, Vector2(75, 15), 11.0)
	y += 22.0 * _g(p, Vector2(-65, -45), 14.0)
	y += 12.0 * _g(p, Vector2(10, -60), 12.0)
	y += 18.0 * _g(p, GLIDE_HILL, 9.0)
	y += 9.0 * _g(p, PLATE_HILL, 7.0)
	# 淺溝：把石頭從山丘引導到開關
	var gz := clampf((z - PLATE_HILL.y - 3.0) / 5.0, 0.0, 1.0) * clampf((PLATE.y - 2.0 - z) / 4.0, 0.0, 1.0)
	y -= 1.4 * exp(-pow(x - PLATE.x, 2.0) / 12.5) * gz
	y -= 12.0 * lake_f
	y += 16.0 * _g(p, LAKE, 5.0)
	var e := maxf(absf(x), absf(z)) / HALF
	y += smoothstep(0.72, 1.0, e) * 30.0
	return lerpf(0.0, y, smoothstep(16.0, 30.0, p.length()))


func _g(p: Vector2, c: Vector2, s: float) -> float:
	return exp(-p.distance_squared_to(c) / (2.0 * s * s))


func _slope(x: float, z: float) -> float:
	return Vector2(h(x + 1, z) - h(x - 1, z), h(x, z + 1) - h(x, z - 1)).length() * 0.5


func _ground_color(x: float, y: float, z: float, slope: float) -> Color:
	var n := noise.get_noise_2d(x * 3.0, z * 3.0) * 0.5 + 0.5
	if y < WATER + 0.7:
		return Color(0.87, 0.8, 0.55)
	if y > 31.0:
		return Color(0.95, 0.96, 1.0)
	if slope > 1.3 or y > 25.0:
		return Color(0.52, 0.5, 0.46).lerp(Color(0.64, 0.6, 0.54), n)
	return Color(0.36, 0.62, 0.22).lerp(Color(0.55, 0.74, 0.3), n)


func _build_terrain() -> void:
	var hts := PackedFloat32Array()
	hts.resize(N * N)
	for j in N:
		for i in N:
			hts[j * N + i] = h(i - HALF, j - HALF)
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in N:
		for i in N:
			var y := hts[j * N + i]
			var sx := hts[j * N + mini(i + 1, N - 1)] - hts[j * N + maxi(i - 1, 0)]
			var sz := hts[mini(j + 1, N - 1) * N + i] - hts[maxi(j - 1, 0) * N + i]
			st.set_color(_ground_color(i - HALF, y, j - HALF, Vector2(sx, sz).length() * 0.5))
			st.add_vertex(Vector3(i - HALF, y, j - HALF))
	for j in N - 1:
		for i in N - 1:
			var a := j * N + i
			st.add_index(a)
			st.add_index(a + 1)
			st.add_index(a + N)
			st.add_index(a + 1)
			st.add_index(a + N + 1)
			st.add_index(a + N)
	st.deindex()  # flat shading, matches Kenney's low-poly look
	st.generate_normals()
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.vertex_color_is_srgb = true
	mat.roughness = 1.0
	var mi := MeshInstance3D.new()
	mi.mesh = st.commit()
	mi.material_override = mat
	add_child(mi)
	var shape := HeightMapShape3D.new()
	shape.map_width = N
	shape.map_depth = N
	shape.map_data = hts
	_static_shape(self, shape, Vector3.ZERO)


func _build_water() -> void:
	var pm := PlaneMesh.new()
	pm.size = Vector2(2 * HALF, 2 * HALF)
	pm.subdivide_width = 80
	pm.subdivide_depth = 80
	var sh := Shader.new()
	sh.code = WATER_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	var mi := MeshInstance3D.new()
	mi.mesh = pm
	mi.material_override = m
	mi.position.y = WATER
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


func _build_bounds() -> void:
	for d: Vector3 in [Vector3.RIGHT, Vector3.LEFT, Vector3.FORWARD, Vector3.BACK]:
		var b := BoxShape3D.new()
		b.size = Vector3(2, 200, 2 * HALF) if d.x != 0 else Vector3(2 * HALF, 200, 2)
		_static_shape(self, b, d * (HALF - 1.0) + Vector3(0, 50, 0))


# ---------------------------------------------------------------- environment

func _setup_input() -> void:
	var keys := {
		"move_forward": [KEY_W, KEY_UP], "move_back": [KEY_S, KEY_DOWN],
		"move_left": [KEY_A, KEY_LEFT], "move_right": [KEY_D, KEY_RIGHT],
		"jump": [KEY_SPACE], "run": [KEY_SHIFT], "cam_left": [KEY_Q], "cam_right": [KEY_E],
	}
	for action: String in keys:
		if not InputMap.has_action(action):
			InputMap.add_action(action)
		for k: Key in keys[action]:
			var ev := InputEventKey.new()
			ev.physical_keycode = k
			InputMap.action_add_event(action, ev)


func _setup_env() -> void:
	var sky_mat := ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.25, 0.5, 0.9)
	sky_mat.sky_horizon_color = Color(0.72, 0.85, 0.95)
	sky_mat.ground_horizon_color = Color(0.72, 0.85, 0.95)
	sky_mat.ground_bottom_color = Color(0.35, 0.45, 0.4)
	var sky := Sky.new()
	sky.sky_material = sky_mat
	var env := Environment.new()
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_energy = 0.45
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.fog_enabled = true
	env.fog_light_color = Color(0.72, 0.84, 0.95)
	env.fog_density = 0.0022
	env.fog_sky_affect = 0.0
	var we := WorldEnvironment.new()
	we.environment = env
	add_child(we)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, -35, 0)
	sun.light_energy = 1.0
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 120.0
	add_child(sun)


# ---------------------------------------------------------------- village

func _build_village() -> void:
	# 營地小村莊：帳篷、營火、木頭長椅、菜園（全部用 Kenney 素材）
	spawn("tent_detailedOpen", Vector3(-6, 0, -5), 3.5, 0.4, true)
	spawn("tent_detailedClosed", Vector3(6, 0, -7), 3.5, -0.5, true)
	spawn("tent_smallOpen", Vector3(10, 0, 1), 3.0, -1.2, true)
	spawn("campfire_logs", Vector3(0, 0, -1), 3.0)
	spawn("log", Vector3(-2.8, 0, 1.2), 3.0, 0.3, true)
	spawn("log", Vector3(2.8, 0, 1.0), 3.0, -0.4, true)
	spawn("log_stack", Vector3(-10, 0, 4), 3.0, 1.0, true)
	spawn("pot_large", Vector3(-4, 0, -9), 3.0)
	for i in 2:
		for j in 3:
			var p := Vector3(12 + i * 3, 0.02, -14 + j * 3)
			spawn("crops_dirtRow", p, 3.0)
			spawn(["crop_pumpkin", "crops_cornStageD", "crop_carrot"][j], p, 3.0, rng.randf() * TAU)
	for k in 3:
		spawn("fence_simple", Vector3(10.5 + k * 3, 0, -4.5), 3.0)
	var fire := OmniLight3D.new()
	fire.light_color = Color(1.0, 0.6, 0.25)
	fire.omni_range = 6.0
	fire.position = Vector3(0, 1.0, -1)
	add_child(fire)


func _build_windmill() -> void:
	var wm := Node3D.new()
	wm.position = WINDMILL
	wm.rotation.y = PI / 2
	add_child(wm)
	_prim(wm, _cyl(1.3, 2.2, 9.0), Color(0.93, 0.87, 0.72), Vector3(0, 4.5, 0))
	_prim(wm, _cyl(0.0, 2.0, 2.6), Color(0.55, 0.15, 0.1), Vector3(0, 10.3, 0))
	_prim(wm, _box(Vector3(1.2, 2.0, 0.3)), Color(0.35, 0.2, 0.1), Vector3(0, 1.0, 2.0))
	_static_shape(wm, _cyl_shape(2.0, 9.0), Vector3(0, 4.5, 0))
	blades = Node3D.new()
	blades.position = Vector3(0, 8.2, 1.9)
	wm.add_child(blades)
	_prim(blades, _cyl(0.35, 0.35, 0.6), Color(0.4, 0.25, 0.12), Vector3.ZERO, Vector3(PI / 2, 0, 0))
	for k in 4:
		var arm := Node3D.new()
		arm.rotation.z = k * PI / 2
		blades.add_child(arm)
		_prim(arm, _box(Vector3(0.25, 6.0, 0.15)), Color(0.4, 0.25, 0.12), Vector3(0, 3.2, 0.3))
		_prim(arm, _box(Vector3(1.4, 4.8, 0.05)), Color(0.97, 0.95, 0.9), Vector3(0.8, 3.6, 0.35))
	spawn("sign", WINDMILL + Vector3(5, 0, 3.5), 2.5, -PI / 2)
	tips.append([WINDMILL, 8.0, ""])  # handled specially in _process


# ---------------------------------------------------------------- puzzles

func _build_puzzles() -> void:
	# 1) 山頂
	_make_gear(Vector3(MOUNTAIN.x, h(MOUNTAIN.x, MOUNTAIN.y) + 1.5, MOUNTAIN.y))

	# 2) 石柱：只能攀爬上去
	var base := h(PILLAR.x, PILLAR.y) - 1.0
	var radii := [3.1, 2.9, 3.2, 3.0]
	for k in 4:
		_prim(self, _cyl(radii[k], radii[k] + 0.15, 4.25), Color(0.55, 0.52, 0.48).darkened(k * 0.05),
				Vector3(PILLAR.x, base + 2.125 + k * 4.25, PILLAR.y))
	_prim(self, _cyl(3.1, 3.1, 0.3), Color(0.4, 0.68, 0.28), Vector3(PILLAR.x, base + 17.05, PILLAR.y))
	_static_shape(self, _cyl_shape(3.0, 17.0), Vector3(PILLAR.x, base + 8.5, PILLAR.y))
	_make_gear(Vector3(PILLAR.x, base + 18.5, PILLAR.y))
	tips.append([Vector3(PILLAR.x, base, PILLAR.y), 9.0, "好高的石柱…對著它按「前進」就能爬上去（會消耗體力）"])

	# 3) 彈跳大香菇 → 空中平台
	var my := h(MUSHROOM.x, MUSHROOM.y)
	_make_mushroom(Vector3(MUSHROOM.x, my, MUSHROOM.y))
	var plat := Vector3(MUSHROOM.x + 5.0, my + 14.0, MUSHROOM.y - 5.0)
	_prim(self, _cyl(3.5, 3.5, 0.6), Color(0.4, 0.7, 0.3), plat)
	_prim(self, _cyl(3.4, 0.8, 3.0), Color(0.5, 0.4, 0.3), plat + Vector3(0, -1.8, 0))
	_static_shape(self, _cyl_shape(3.5, 0.6), plat)
	spawn("tree_oak", plat + Vector3(-1.8, 0.3, 1.2), 2.5)
	spawn("flower_redA", plat + Vector3(1.5, 0.3, 1.5), 2.0)
	_make_gear(plat + Vector3(0, 1.8, 0))
	tips.append([Vector3(MUSHROOM.x, my, MUSHROOM.y), 7.0, "踩上大香菇試試看！"])

	# 4) 湖中小島：從山丘滑翔過去
	var iy := h(LAKE.x, LAKE.y)
	_make_gear(Vector3(LAKE.x, iy + 1.5, LAKE.y))
	spawn("tree_oak", Vector3(LAKE.x + 2.0, iy - 0.2, LAKE.y + 1.0), 3.0)
	var hill := Vector3(GLIDE_HILL.x, h(GLIDE_HILL.x, GLIDE_HILL.y), GLIDE_HILL.y)
	spawn("tent_detailedOpen", hill + Vector3(3, -0.2, 2), 3.0, 0.6)
	spawn("campfire_stones", hill + Vector3(-1, -0.1, 3), 2.5)
	tips.append([hill, 8.0, "在高處起跳，空中再按一次「空白鍵」打開滑翔翼！"])

	# 5) 推石頭壓開關
	var pp := Vector3(PLATE.x, h(PLATE.x, PLATE.y), PLATE.y)
	plate_pos = pp
	var ped := _prim(self, _cyl(3.0, 4.5, 0.5), Color(0.55, 0.52, 0.48), pp + Vector3(0, 0.25, 0))
	_static_shape(self, ped.mesh.create_convex_shape(), pp + Vector3(0, 0.25, 0))
	plate_mat = _mat(Color(0.2, 0.55, 1.0), 2.0)
	var ring := MeshInstance3D.new()
	ring.mesh = flat_mesh(_cyl(2.7, 2.7, 0.2))
	ring.material_override = plate_mat
	ring.position = pp + Vector3(0, 0.55, 0)
	add_child(ring)
	_prim(self, _cyl(2.1, 2.1, 0.24), Color(0.62, 0.62, 0.65), pp + Vector3(0, 0.56, 0))
	for k in 4:
		var ang := k * TAU / 4.0 + PI / 4.0
		_prim(self, _cyl(0.25, 0.3, 1.0), Color(0.5, 0.47, 0.43), pp + Vector3(cos(ang) * 3.6, 0.9, sin(ang) * 3.6))
	# 護欄岩石：沿著淺溝兩側
	for gz: float in [30.0, 33.0, 36.0]:
		for side: float in [-1.0, 1.0]:
			var rx := PLATE.x + side * 4.2
			spawn("rock_tallC" if int(gz) % 2 == 0 else "rock_largeB", Vector3(rx, h(rx, gz) - 0.3, gz), 3.2, side * gz, true)
	var area := Area3D.new()
	area.position = pp + Vector3(0, 1.3, 0)
	add_child(area)
	var acs := CollisionShape3D.new()
	acs.shape = _cyl_shape(2.8, 2.0)
	area.add_child(acs)
	area.body_entered.connect(_on_plate_body.bind(pp))

	rock_start = Vector3(PLATE_HILL.x, h(PLATE_HILL.x, PLATE_HILL.y) + 1.4, PLATE_HILL.y)
	rock = RigidBody3D.new()
	rock.add_to_group("rock")
	rock.mass = 3.0
	rock.linear_damp = 0.2
	rock.angular_damp = 0.5
	var pmat := PhysicsMaterial.new()
	pmat.friction = 0.9
	pmat.bounce = 0.05
	rock.physics_material_override = pmat
	var rcs := CollisionShape3D.new()
	var rs := SphereShape3D.new()
	rs.radius = 1.3
	rcs.shape = rs
	rock.add_child(rcs)
	_prim(rock, _sphere(1.3), Color(0.58, 0.56, 0.52), Vector3.ZERO)
	for k in 5:
		var d := Vector3(rng.randf_range(-1, 1), rng.randf_range(-1, 1), rng.randf_range(-1, 1)).normalized()
		_prim(rock, _sphere(0.35), Color(0.35, 0.55, 0.3), d * 1.1)
	rock.position = rock_start
	add_child(rock)
	rock.sleeping = true
	tips.append([rock_start, 7.0, "這顆大石頭推得動耶…山下好像有個藍色開關？"])

	# 上升氣流
	_make_updraft(UPDRAFT)


func _on_plate_body(body: Node3D, pp: Vector3) -> void:
	if plate_done or not body.is_in_group("rock"):
		return
	plate_done = true
	# lock the rock onto the switch so it visibly stays there
	rock.freeze = true
	var tw := create_tween()
	tw.tween_property(rock, "global_position", pp + Vector3(0, 2.0, 0), 0.25)
	plate_mat.albedo_color = Color(0.3, 0.9, 0.4)
	plate_mat.emission = Color(0.3, 0.9, 0.4)
	_make_gear(pp + Vector3(4.0, 1.5, 0))
	_ding(0.8)
	show_hint("喀嚓！石頭壓住開關，齒輪出現了！")


func _make_gear(pos: Vector3) -> void:
	var a := Area3D.new()
	a.position = pos
	add_child(a)
	var cs := CollisionShape3D.new()
	var sp := SphereShape3D.new()
	sp.radius = 1.3
	cs.shape = sp
	a.add_child(cs)
	var vis := Node3D.new()
	vis.name = "Vis"
	a.add_child(vis)
	var gold := Color(1.0, 0.78, 0.2)
	_prim(vis, _cyl(0.6, 0.6, 0.25), gold, Vector3.ZERO, Vector3(PI / 2, 0, 0), 1.5)
	for k in 8:
		var ang := k * TAU / 8.0
		_prim(vis, _box(Vector3(0.28, 0.28, 0.25)), gold, Vector3(cos(ang), sin(ang), 0) * 0.72, Vector3(0, 0, ang), 1.5)
	_prim(vis, _cyl(0.2, 0.2, 0.3), Color(0.35, 0.25, 0.1), Vector3.ZERO, Vector3(PI / 2, 0, 0))
	var light := OmniLight3D.new()
	light.light_color = gold
	light.omni_range = 7.0
	light.light_energy = 2.0
	a.add_child(light)
	var beam := MeshInstance3D.new()
	beam.mesh = _cyl(0.25, 0.25, 80.0)
	beam.position.y = 40.0
	var bm := StandardMaterial3D.new()
	bm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	bm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	bm.albedo_color = Color(1.0, 0.85, 0.3, 0.35)
	beam.material_override = bm
	beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	a.add_child(beam)
	a.body_entered.connect(_on_gear_body.bind(a))
	gears.append(a)


func _on_gear_body(body: Node3D, gear: Area3D) -> void:
	if body != player or not gears.has(gear):
		return
	gears.erase(gear)
	gear.queue_free()
	gears_found += 1
	gear_label.text = "風車齒輪  %d / %d" % [gears_found, GEARS_TOTAL]
	_ding(1.0)
	if gears_found < GEARS_TOTAL:
		show_hint("叮！拿到風車齒輪 %d / %d" % [gears_found, GEARS_TOTAL])
	else:
		show_hint("5 個齒輪都到手了！回營地修好大風車吧～", 5.0)


func _make_mushroom(pos: Vector3) -> void:
	_prim(self, _cyl(0.6, 0.8, 2.6), Color(0.96, 0.92, 0.82), pos + Vector3(0, 1.3, 0))
	var cap := _prim(self, _sphere(2.2, 1.6), Color(0.9, 0.2, 0.18), pos + Vector3(0, 2.6, 0))
	for k in 6:
		var ang := k * TAU / 6.0
		_prim(cap, _sphere(0.3), Color.WHITE, Vector3(cos(ang) * 1.4, 0.62, sin(ang) * 1.4))
	_prim(cap, _sphere(0.35), Color.WHITE, Vector3(0, 0.78, 0))
	var body := _static_shape(self, _cyl_shape(0.7, 2.4), pos + Vector3(0, 1.2, 0))
	var top := CollisionShape3D.new()
	top.shape = _cyl_shape(2.1, 0.8)
	top.position.y = 1.8
	body.add_child(top)
	var area := Area3D.new()
	area.position = pos + Vector3(0, 3.6, 0)
	add_child(area)
	var acs := CollisionShape3D.new()
	acs.shape = _cyl_shape(2.0, 0.6)
	area.add_child(acs)
	area.body_entered.connect(func(b: Node3D) -> void:
		if b == player:
			player.bounce(24.0)
			_ding(0.5)
			var tw := create_tween()
			tw.tween_property(cap, "scale", Vector3(1.2, 0.7, 1.2), 0.08)
			tw.tween_property(cap, "scale", Vector3.ONE, 0.25).set_trans(Tween.TRANS_ELASTIC))
	for k in 5:
		spawn("mushroom_redGroup", pos + Vector3(rng.randf_range(-4, 4), 0, rng.randf_range(-4, 4)), 2.0, rng.randf() * TAU)


func _make_updraft(p: Vector2) -> void:
	var base := Vector3(p.x, h(p.x, p.y), p.y)
	var area := Area3D.new()
	area.position = base + Vector3(0, 20, 0)
	add_child(area)
	var cs := CollisionShape3D.new()
	cs.shape = _cyl_shape(3.5, 40.0)
	area.add_child(cs)
	area.body_entered.connect(func(b: Node3D) -> void:
		if b == player:
			player.updraft = 40.0)
	area.body_exited.connect(func(b: Node3D) -> void:
		if b == player:
			player.updraft = 0.0)
	var col := MeshInstance3D.new()
	col.mesh = _cyl(3.5, 3.5, 40.0)
	var cm := StandardMaterial3D.new()
	cm.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	cm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	cm.cull_mode = BaseMaterial3D.CULL_DISABLED
	cm.albedo_color = Color(1, 1, 1, 0.08)
	col.material_override = cm
	col.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	area.add_child(col)
	var fx := CPUParticles3D.new()
	fx.position = base
	fx.amount = 60
	fx.lifetime = 5.0
	fx.emission_shape = CPUParticles3D.EMISSION_SHAPE_SPHERE
	fx.emission_sphere_radius = 3.0
	fx.direction = Vector3.UP
	fx.spread = 8.0
	fx.gravity = Vector3.ZERO
	fx.initial_velocity_min = 6.0
	fx.initial_velocity_max = 9.0
	fx.mesh = _leaf_mesh(Color(0.6, 0.9, 0.4))
	add_child(fx)
	for k in 8:
		var ang := k * TAU / 8.0
		spawn("rock_smallA", base + Vector3(cos(ang), 0, sin(ang)) * 4.0, 2.0, ang)
	tips.append([base, 6.0, "有風往上吹！打開滑翔翼乘著上升氣流飛高吧"])


# ---------------------------------------------------------------- nature

func spawn(model_name: String, pos: Vector3, s := 1.0, rot := 0.0, collide := false) -> Node3D:
	var n: Node3D = (load(NATURE + model_name + ".glb") as PackedScene).instantiate()
	n.position = pos
	n.scale = Vector3.ONE * s
	n.rotation.y = rot
	add_child(n)
	_regreen(n)
	if collide:
		for mi in n.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).create_trimesh_collision()
	return n


var _regreened := {}

## Kenney's palette is teal; shift teal/cyan materials toward a warmer grass green to match the terrain.
func _regreen(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if m == null or _regreened.has(m):
				continue
			_regreened[m] = true
			var c := m.albedo_color
			if c.g > c.r * 1.2 and c.b > c.g * 0.55:
				m.albedo_color = Color.from_hsv(0.28 + (c.h - 0.45) * 0.3, minf(c.s * 1.05, 0.75), c.v * 0.85)


func _near_poi(p: Vector2, r: float) -> bool:
	for c: Vector2 in [PILLAR, MUSHROOM, MUSHROOM + Vector2(5, -5), PLATE_HILL, PLATE, UPDRAFT, LAKE, GLIDE_HILL,
			Vector2(PLATE.x, (PLATE.y + PLATE_HILL.y) * 0.5), Vector2(WINDMILL.x, WINDMILL.z)]:
		if p.distance_to(c) < r:
			return true
	return false


func _scatter_nature() -> void:
	for k in 260:
		var x := rng.randf_range(-92, 92)
		var z := rng.randf_range(-92, 92)
		var y := h(x, z)
		if Vector2(x, z).length() < 26.0 or _near_poi(Vector2(x, z), 8.0):
			continue
		if y < WATER + 1.0 or y > 27.0 or _slope(x, z) > 0.7:
			continue
		var names: Array = PINES if y > 10.0 else TREES
		var s := rng.randf_range(3.0, 5.0)
		spawn(names[rng.randi() % names.size()], Vector3(x, y - 0.1, z), s, rng.randf() * TAU)
		_static_shape(self, _cyl_shape(0.12 * s, 6.0), Vector3(x, y + 3.0, z))
	for k in 50:
		var x := rng.randf_range(-90, 90)
		var z := rng.randf_range(-90, 90)
		var y := h(x, z)
		if Vector2(x, z).length() < 22.0 or _near_poi(Vector2(x, z), 7.0) or y < WATER:
			continue
		spawn(ROCKS[rng.randi() % ROCKS.size()], Vector3(x, y - 0.3, z), rng.randf_range(2.0, 4.0), rng.randf() * TAU, true)
	for k in 400:
		var x := rng.randf_range(-90, 90)
		var z := rng.randf_range(-90, 90)
		var y := h(x, z)
		if y < WATER + 0.8 or y > 24.0 or _slope(x, z) > 0.8 or Vector2(x, z).length() < 12.0:
			continue
		spawn(DECOR[rng.randi() % DECOR.size()], Vector3(x, y, z), rng.randf_range(2.0, 3.0), rng.randf() * TAU)
	for k in 40:
		var p := LAKE + Vector2(rng.randf_range(-26, 26), rng.randf_range(-26, 26))
		if h(p.x, p.y) < WATER - 0.8 and p.distance_to(LAKE) > 7.0:
			spawn("lily_large" if k % 2 else "lily_small", Vector3(p.x, WATER + 0.03, p.y), 3.0, rng.randf() * TAU)


# ---------------------------------------------------------------- player & HUD

func _spawn_player() -> void:
	player = PlayerScript.new()
	player.position = Vector3(0.0, 1.0, 12.0)
	player.water_level = WATER
	add_child(player)
	player.drowned.connect(func() -> void: show_hint("咕嚕咕嚕…被沖回岸上了", 2.0))


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["PingFang TC", "Heiti TC", "Noto Sans CJK TC", "sans-serif"])
	var theme := Theme.new()
	theme.default_font = font
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.theme = theme
	layer.add_child(root)

	gear_label = _label(root, "風車齒輪  0 / %d" % GEARS_TOTAL, 30)
	gear_label.position = Vector2(24, 16)

	var help := _label(root, "WASD 移動　Shift 跑步　空白鍵 跳／空中開滑翔翼\n點畫面鎖定滑鼠轉視角（Esc 解除）　Q / E 轉視角\n對著陡坡或石柱按前進 → 攀爬", 16)
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	help.anchor_left = 1.0
	help.anchor_right = 1.0
	help.offset_left = -620
	help.offset_right = -20
	help.offset_top = 16

	hint_label = _label(root, "", 26)
	hint_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	hint_label.anchor_right = 1.0
	hint_label.anchor_top = 1.0
	hint_label.anchor_bottom = 1.0
	hint_label.offset_top = -170
	hint_label.offset_bottom = -80

	stamina_bar = ProgressBar.new()
	stamina_bar.max_value = PlayerScript.MAX_STAMINA
	stamina_bar.show_percentage = false
	stamina_fill = StyleBoxFlat.new()
	stamina_fill.bg_color = Color(0.45, 0.9, 0.35)
	stamina_fill.set_corner_radius_all(6)
	var bg := StyleBoxFlat.new()
	bg.bg_color = Color(0, 0, 0, 0.45)
	bg.set_corner_radius_all(6)
	stamina_bar.add_theme_stylebox_override("fill", stamina_fill)
	stamina_bar.add_theme_stylebox_override("background", bg)
	stamina_bar.anchor_left = 0.5
	stamina_bar.anchor_right = 0.5
	stamina_bar.anchor_top = 0.5
	stamina_bar.anchor_bottom = 0.5
	stamina_bar.offset_left = 70
	stamina_bar.offset_right = 210
	stamina_bar.offset_top = -40
	stamina_bar.offset_bottom = -26
	root.add_child(stamina_bar)


func _label(parent: Control, text: String, size: int) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", Color.WHITE)
	l.add_theme_color_override("font_outline_color", Color(0.1, 0.15, 0.1))
	l.add_theme_constant_override("outline_size", 8)
	parent.add_child(l)
	return l


func show_hint(text: String, duration := 3.0) -> void:
	hint_label.text = text
	hint_time = duration


func _process(delta: float) -> void:
	var t := Time.get_ticks_msec() * 0.003
	for g in gears:
		var vis := g.get_node("Vis") as Node3D
		vis.rotate_y(delta * 2.0)
		vis.position.y = sin(t) * 0.2
	if repaired:
		blades.rotate_z(delta * 1.5)

	stamina_bar.value = player.stamina
	stamina_bar.visible = player.stamina < PlayerScript.MAX_STAMINA - 0.5
	stamina_fill.bg_color = Color(0.95, 0.35, 0.3) if player.exhausted else Color(0.45, 0.9, 0.35)
	hint_time -= delta
	hint_label.modulate.a = clampf(hint_time, 0.0, 1.0)

	var pos := player.global_position
	if not repaired and pos.distance_to(WINDMILL) < 8.0:
		if gears_found >= GEARS_TOTAL:
			_repair()
		elif hint_time < 0.5:
			show_hint("大風車少了 %d 個齒輪，轉不起來…" % (GEARS_TOTAL - gears_found), 2.5)
	for tip: Array in tips:
		if tip[2] != "" and pos.distance_to(tip[0]) < tip[1]:
			show_hint(tip[2], 4.0)
			tip[2] = ""


func _physics_process(_delta: float) -> void:
	if rock and not plate_done and (rock.global_position.y < WATER - 4.0 or rock.global_position.length() > 140.0):
		rock.linear_velocity = Vector3.ZERO
		rock.angular_velocity = Vector3.ZERO
		rock.global_position = rock_start
		show_hint("石頭滾不見了…已經放回山丘上")


func _repair() -> void:
	repaired = true
	for i in 3:
		get_tree().create_timer(i * 0.18).timeout.connect(_ding.bind([1.0, 1.26, 1.5][i]))
	show_hint("大風車轉起來了！營地恢復活力～謝謝你！\n（Demo 完成）", 8.0)
	var fx := CPUParticles3D.new()
	fx.position = WINDMILL + Vector3(0, 9, 0)
	fx.one_shot = true
	fx.amount = 200
	fx.lifetime = 4.0
	fx.explosiveness = 0.9
	fx.direction = Vector3.UP
	fx.spread = 70.0
	fx.initial_velocity_min = 8.0
	fx.initial_velocity_max = 16.0
	fx.gravity = Vector3(0, -6, 0)
	fx.mesh = _leaf_mesh(Color.WHITE)
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.33, 0.66, 1.0])
	g.colors = PackedColorArray([Color(1, 0.3, 0.3), Color(1, 0.85, 0.2), Color(0.3, 0.6, 1), Color(1, 0.5, 0.8)])
	fx.color_initial_ramp = g
	add_child(fx)
	fx.emitting = true


# ---------------------------------------------------------------- helpers

func _make_ding(freq: float) -> AudioStreamWAV:
	var rate := 22050
	var count := int(rate * 0.6)
	var data := PackedByteArray()
	data.resize(count * 2)
	for i in count:
		var tt := float(i) / rate
		var v := (sin(TAU * freq * tt) + 0.4 * sin(TAU * freq * 2.0 * tt)) * exp(-tt * 7.0) * 0.4
		data.encode_s16(i * 2, int(clampf(v, -1.0, 1.0) * 32767.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = rate
	w.data = data
	return w


func _ding(pitch: float) -> void:
	var p := AudioStreamPlayer.new()
	p.stream = ding_stream
	p.pitch_scale = pitch
	add_child(p)
	p.play()
	p.finished.connect(p.queue_free)


func _leaf_mesh(c: Color) -> QuadMesh:
	var q := QuadMesh.new()
	q.size = Vector2(0.35, 0.22)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.vertex_color_use_as_albedo = true
	m.albedo_color = c
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	m.cull_mode = BaseMaterial3D.CULL_DISABLED
	q.material = m
	return q


func _mat(c: Color, emit := 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.8
	if emit > 0.0:
		m.emission_enabled = true
		m.emission = c
		m.emission_energy_multiplier = emit
	return m


func _prim(parent: Node, mesh: Mesh, c: Color, pos: Vector3, rot := Vector3.ZERO, emit := 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = flat_mesh(mesh)
	mi.material_override = _mat(c, emit)
	mi.position = pos
	mi.rotation = rot
	parent.add_child(mi)
	return mi


func _static_shape(parent: Node, shape: Shape3D, pos: Vector3) -> StaticBody3D:
	var b := StaticBody3D.new()
	b.position = pos
	parent.add_child(b)
	var cs := CollisionShape3D.new()
	cs.shape = shape
	b.add_child(cs)
	return b


func _cyl(top: float, bottom: float, height: float) -> CylinderMesh:
	var m := CylinderMesh.new()
	m.top_radius = top
	m.bottom_radius = bottom
	m.height = height
	m.radial_segments = 10
	m.rings = 1
	return m


func _cyl_shape(r: float, height: float) -> CylinderShape3D:
	var s := CylinderShape3D.new()
	s.radius = r
	s.height = height
	return s


func _box(s: Vector3) -> BoxMesh:
	var m := BoxMesh.new()
	m.size = s
	return m


func _sphere(r: float, height := -1.0) -> SphereMesh:
	var m := SphereMesh.new()
	m.radius = r
	m.height = r * 2.0 if height < 0.0 else height
	m.radial_segments = 12
	m.rings = 6
	return m


## Deindex + regenerate normals → faceted low-poly shading.
static func flat_mesh(mesh: Mesh) -> ArrayMesh:
	var st := SurfaceTool.new()
	st.create_from(mesh, 0)
	st.deindex()
	st.generate_normals()
	return st.commit()
