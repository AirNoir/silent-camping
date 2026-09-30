extends Node3D
## 森林 Diorama：一塊方形浮空地台（側面土層），上面是起伏草地、小徑、小池塘、營地和茂密樹林。
## 長焦鏡頭 + 景深模糊做微縮模型感；滑鼠拖曳環繞、滾輪縮放，閒置時緩慢自轉。
## 植物模型來自 Kenney Nature Kit，材質依名稱統一換成森林配色。

const NATURE := "res://assets/nature/"
const SIZE := 44.0           # 地台邊長，世界範圍 [-22, 22]
const STEP := 0.35           # 地形頂點間距
const BASE_Y := -7.0         # 地台底部
const MASK_RES := 256
const POND := Vector2(10.0, 9.0)
const WATER_Y := -1.5
const HILL := Vector2(-12.0, -12.0)
const CAMP := Vector2(-6.0, -4.5)
const TENT := Vector2(-8.4, -6.0)
const FIRE := Vector2(-4.6, -3.6)
const TABLE := Vector2(-9.2, -2.2)
const VAN := Vector2(-10.5, 4.6)
const VAN_ROT := 0.3805   # 沿小徑方向 (10, -4)

const PALETTE := {
	"leafsGreen": Color(0.36, 0.63, 0.30),
	"leafsDark": Color(0.22, 0.47, 0.30),
	"leafsFall": Color(0.85, 0.55, 0.25),
	"woodBark": Color(0.44, 0.31, 0.21),
	"woodBarkDark": Color(0.35, 0.24, 0.17),
	"woodInner": Color(0.84, 0.71, 0.50),
	"grass": Color(0.40, 0.66, 0.30),
	"dirt": Color(0.55, 0.45, 0.34),
	"stone": Color(0.62, 0.62, 0.60),
	"rock": Color(0.55, 0.53, 0.50),
	"colorRed": Color(0.85, 0.25, 0.22),
	"colorYellow": Color(0.98, 0.82, 0.35),
	"colorPurple": Color(0.62, 0.45, 0.85),
	"_defaultMat": Color(0.95, 0.94, 0.90),
}

## 營地道具的材質（露營車／帳篷）：不套森林配色，只調質感
const PROP_MATS := {
	"glass": {"roughness": 0.2, "metallic": 0.0, "alpha": 0.14, "albedo": Color(0.78, 0.88, 0.94), "specular": 0.15},
	"headlightGlass": {"roughness": 0.05, "metallic": 0.0, "alpha": 0.45, "albedo": Color(0.85, 0.92, 1.0)},
	"interiorDark": {"roughness": 1.0, "two_sided": true},
	"chrome": {"roughness": 0.22, "metallic": 0.9},
	"darkMetal": {"roughness": 0.45, "metallic": 0.6},
	"vanPaint": {"roughness": 0.35, "albedo": Color(0.78, 0.17, 0.15)}, "vanCream": {"roughness": 0.4}, "tailRed": {"roughness": 0.3},
	"solar": {"roughness": 0.15, "metallic": 0.4},
	# 玩具塑膠光澤：低粗糙度 + clearcoat
	"vanMint": {"roughness": 0.3, "clearcoat": 0.4, "albedo": Color(0.46, 0.90, 0.74), "two_sided": true},
	"vanCreamY": {"roughness": 0.3, "clearcoat": 0.4, "albedo": Color(1.0, 0.92, 0.58), "two_sided": true},
	"bagCoral": {"roughness": 0.85}, "coolerBlue": {"roughness": 0.35, "clearcoat": 0.3},
	"tentGreen": {"roughness": 0.95}, "tentBeige": {"roughness": 0.95}, "tentFloor": {"roughness": 0.9}, "tentMesh": {"roughness": 1.0},
	"rubber": {"roughness": 0.85}, "canvas": {"roughness": 0.95}, "canvasTrim": {"roughness": 0.95},
}

const GROUND_SHADER := """
shader_type spatial;
uniform vec3 grass_a : source_color = vec3(0.32, 0.54, 0.22);
uniform vec3 grass_b : source_color = vec3(0.44, 0.66, 0.28);
uniform vec3 moss : source_color = vec3(0.28, 0.48, 0.23);
uniform vec3 dirt : source_color = vec3(0.56, 0.42, 0.26);
uniform vec3 sand : source_color = vec3(0.82, 0.74, 0.54);
uniform vec3 soil_dark : source_color = vec3(0.33, 0.23, 0.16);
uniform vec3 soil_light : source_color = vec3(0.52, 0.40, 0.28);
uniform sampler2D noise_tex : filter_linear, repeat_enable;
uniform sampler2D path_tex : filter_linear, repeat_disable;
uniform float world_size = 44.0;
uniform float water_y = -1.5;
uniform vec2 pond_center = vec2(10.0, 9.0);
uniform int dbg = 0;
varying vec3 wpos;
varying vec3 wnrm;
void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}
void fragment() {
	vec2 uvw = wpos.xz / world_size + 0.5;
	float n1 = texture(noise_tex, wpos.xz * 0.04).r;
	float n2 = texture(noise_tex, wpos.xz * 0.25).r;
	float n3 = texture(noise_tex, wpos.xz * 1.3).r;
	vec3 g = mix(grass_a, grass_b, smoothstep(0.3, 0.7, n1));
	g = mix(g, moss, smoothstep(0.55, 0.8, n2) * 0.4);
	g *= 0.95 + 0.10 * n3;
	float p = texture(path_tex, uvw).r;
	vec3 col = mix(g, dirt * (0.9 + 0.2 * n3), smoothstep(0.25, 0.7, p + (n3 - 0.5) * 0.25));
	float pond = 1.0 - smoothstep(6.0, 9.0, distance(wpos.xz, pond_center));
	float beach = (1.0 - smoothstep(water_y + 0.1, water_y + 1.0, wpos.y)) * pond;
	col = mix(col, sand * (0.9 + 0.2 * n3), beach);
	float side = 1.0 - smoothstep(0.15, 0.45, wnrm.y);   // 只有近垂直的面才是土層（地台側面）
	vec2 wall_uv = vec2(wpos.x + wpos.z, wpos.y);
	float nw = texture(noise_tex, wall_uv * 0.08).r;
	float nw2 = texture(noise_tex, wall_uv * 0.6).r;
	float strata = sin(wpos.y * 2.0 + nw * 4.0) * 0.5 + 0.5;
	vec3 soil = mix(soil_dark, soil_light, strata * 0.6 + nw2 * 0.4);
	soil = mix(soil, soil_light * 1.15, smoothstep(0.78, 0.9, nw2) * 0.5);  // 小石子
	col = mix(col, soil, side);
	if (dbg == 1) { col = grass_a; }
	if (dbg == 2) { col = vec3(n1, n2, n3); }
	if (dbg == 3) { col = vec3(p, side, beach); }
	ALBEDO = col;
	ROUGHNESS = 1.0;
	SPECULAR = 0.05;
}
"""

const GRASS_SHADER := """
shader_type spatial;
render_mode cull_disabled;
// 顏色與地面 shader 同一套：草是地面的延伸，不是另一個物件（BotW 的做法）
uniform vec3 grass_a : source_color = vec3(0.32, 0.54, 0.22);
uniform vec3 grass_b : source_color = vec3(0.44, 0.66, 0.28);
uniform vec3 moss : source_color = vec3(0.28, 0.48, 0.23);
uniform sampler2D noise_tex : filter_linear, repeat_enable;
uniform vec2 wind_dir = vec2(0.8, 0.5);
uniform float wind = 0.06;
varying float hgt;
varying vec3 wpos;
void vertex() {
	hgt = UV.y;
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	// 整片往同一個方向倒，慢慢波動
	float t = TIME * 0.9;
	float w = 0.5 + 0.5 * sin(t + dot(wpos.xz, wind_dir) * 0.35) + 0.25 * sin(t * 1.6 + wpos.x * 0.9 + wpos.z * 0.7);
	VERTEX.xz += wind_dir * w * wind * hgt * hgt;
}
void fragment() {
	// Godot 對 cull_disabled 材質會把背面的法線翻轉；這裡直接指定「世界正上方」，正反面都跟地面一樣受光
	NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	float n1 = texture(noise_tex, wpos.xz * 0.04).r;
	float n2 = texture(noise_tex, wpos.xz * 0.25).r;
	vec3 g = mix(grass_a, grass_b, smoothstep(0.3, 0.7, n1));
	g = mix(g, moss, smoothstep(0.55, 0.8, n2) * 0.4);
	// 根部只比地面暗一點（假 AO），尖端略亮
	g *= mix(0.86, 1.08, hgt);
	ALBEDO = g * COLOR.rgb;
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
}
"""

const LEAF_SHADER := """
shader_type spatial;
// 葉子的法線在 Blender 已改成「樹冠球面法線」，兩面共用、不翻轉；wrap 讓明暗交界更柔
render_mode cull_disabled, diffuse_lambert_wrap;
uniform vec4 albedo : source_color = vec4(1.0);
uniform float wind = 0.035;
varying vec3 wnrm;
void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float t = TIME * 1.3;
	float w = sin(t + wp.x * 0.5 + wp.z * 0.3) + 0.5 * sin(t * 1.9 + wp.y * 0.7 + wp.z * 0.4);
	VERTEX.xz += w * wind * clamp(VERTEX.y * 0.6, 0.0, 1.0);
	wnrm = MODEL_NORMAL_MATRIX * NORMAL;
}
void fragment() {
	// 用 Blender 烘好的樹冠球面法線，正反面同一個方向（Godot 預設會翻背面法線，這裡繞過）
	NORMAL = normalize((VIEW_MATRIX * vec4(wnrm, 0.0)).xyz);
	ALBEDO = albedo.rgb * COLOR.rgb;
	ROUGHNESS = 1.0;
	SPECULAR = 0.08;
}
"""

const FLAME_SHADER := """
shader_type spatial;
render_mode unshaded, cull_disabled;
uniform vec4 albedo : source_color = vec4(1.0, 0.5, 0.1, 1.0);
uniform float glow = 4.0;
uniform float seed = 0.0;
void vertex() {
	// 火焰底部不動、越往上擺得越多；整體高度呼吸、底部微微脹縮
	float t = TIME * 6.0 + seed;
	float h = clamp(VERTEX.y / 0.5, 0.0, 1.0);
	VERTEX.x += 0.06 * h * sin(t * 1.7 + VERTEX.y * 9.0);
	VERTEX.z += 0.05 * h * cos(t * 1.3 + VERTEX.y * 7.0);
	VERTEX.y *= 1.0 + 0.18 * h * sin(t * 2.3);
	VERTEX.xz *= 1.0 + 0.10 * sin(t * 2.9 + 0.7) * (1.0 - h);
}
void fragment() {
	ALBEDO = albedo.rgb;
	EMISSION = albedo.rgb * glow;
}
"""

const WATER_SHADER := """
shader_type spatial;
render_mode blend_mix, cull_disabled;
uniform vec4 tint : source_color = vec4(0.30, 0.62, 0.80, 0.72);
varying vec3 wpos;
void vertex() {
	VERTEX.y += sin(VERTEX.x * 2.0 + TIME * 1.2) * 0.02 + cos(VERTEX.z * 1.7 + TIME) * 0.02;
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}
void fragment() {
	float r = sin(wpos.x * 2.2 + TIME * 0.9) * 0.5 + sin(wpos.z * 1.8 - TIME * 0.7 + wpos.x * 0.6) * 0.5;
	float fr = pow(1.0 - clamp(dot(NORMAL, VIEW), 0.0, 1.0), 3.0);
	ALBEDO = tint.rgb + r * 0.025;
	ALPHA = mix(tint.a, 0.92, fr);
	ROUGHNESS = 0.08;
	SPECULAR = 0.6;
}
"""

var noise := FastNoiseLite.new()
var forest_noise := FastNoiseLite.new()
var rng := RandomNumberGenerator.new()
var path_img: Image
var path_pts := PackedVector2Array()
var _mesh_cache := {}
var tent_rot := 0.0
var rug_center := Vector2.ZERO
var leaf_shader: Shader
var tree_dir := "gen"   # assets/<tree_dir>/tree_*.glb
var bench := false
var cam_locked := false   # --orbit / --cam 截圖時忽略滑鼠，免得錄影中被轉走
# 日／黃昏／夜切換（N 鍵循環）
enum TimeOfDay { DAY, DUSK, NIGHT }
var tod := TimeOfDay.DAY
var night := false
var tod_duration := 30.0       # 漸變秒數（demo 模式會暫時壓短）
var tod_cur := {}              # 目前（插值中的）狀態
var tod_from := {}
var tod_to := {}
var tod_t := 0.0
var tod_active := false
var tod_debug := false
# 自動循環（A 鍵）：每個時段停留 AUTO_HOLD 秒，再花 TOD_DURATION 秒漸變到下一個
var auto_cycle := false
const AUTO_HOLD := 60.0
var auto_timer := 0.0
# 展示影片模式（--demo=秒數）：鏡頭自動運鏡 + 壓縮的日→黃昏→夜，結束自動關閉
var demo_len := 0.0
var demo_t := 0.0
var demo_dusk_started := false
var demo_night_started := false
var help_label: Label
# 火光／燈泡閃爍
var flame_mats: Array[ShaderMaterial] = []
var flame_shader: Shader
var bulb_mats_all: Array[StandardMaterial3D] = []

## 三個時段的所有參數（float / Color / Vector3 都可以線性插值）
const TOD_PRESETS := {
	TimeOfDay.DAY: {
		"sky_top": Color(0.66, 0.80, 0.98), "sky_h": Color(0.88, 0.92, 0.97), "gnd_h": Color(0.86, 0.88, 0.88), "gnd_b": Color(0.60, 0.62, 0.60),
		"sky_e": 1.35, "sun_disc": 0.0,
		"amb_c": Color(0.74, 0.82, 0.94), "amb_e": 0.24, "exposure": 0.74, "glow_i": 0.2, "bloom": 0.02, "glow_thr": 1.4,
		"vfog_d": 0.0, "vfog_c": Color(1.0, 1.0, 1.0),
		"sun_rot": Vector3(-44, 32, 0), "sun_c": Color(1.0, 0.95, 0.85), "sun_e": 1.3, "sun_body": 0.0,
		"head": 0.0, "cabin": 1.0, "fire": 1.6, "fire_r": 4.5, "lantern": 0.0, "tent": 0.0, "bulbs": 0.5,
		"ff": 0.0, "head_glow": 0.0, "tail_glow": 0.0,
	},
	TimeOfDay.DUSK: {
		"sky_top": Color(0.30, 0.34, 0.62), "sky_h": Color(1.0, 0.72, 0.46), "gnd_h": Color(0.78, 0.58, 0.48), "gnd_b": Color(0.30, 0.26, 0.30),
		"sky_e": 1.0, "sun_disc": 12.0,
		"amb_c": Color(0.52, 0.54, 0.76), "amb_e": 0.32, "exposure": 0.86, "glow_i": 0.35, "bloom": 0.05, "glow_thr": 1.1,
		"vfog_d": 0.0025, "vfog_c": Color(1.0, 0.86, 0.72),
		"sun_rot": Vector3(-18, 62, 0), "sun_c": Color(1.0, 0.74, 0.44), "sun_e": 1.7, "sun_body": 0.0,
		"head": 3.0, "cabin": 1.6, "fire": 3.0, "fire_r": 5.5, "lantern": 1.4, "tent": 1.0, "bulbs": 2.2,
		"ff": 1.2, "head_glow": 2.0, "tail_glow": 1.2,
	},
	TimeOfDay.NIGHT: {
		"sky_top": Color(0.02, 0.03, 0.09), "sky_h": Color(0.09, 0.11, 0.22), "gnd_h": Color(0.06, 0.07, 0.12), "gnd_b": Color(0.02, 0.02, 0.04),
		"sky_e": 0.55, "sun_disc": 0.0,
		"amb_c": Color(0.30, 0.36, 0.60), "amb_e": 0.14, "exposure": 0.9, "glow_i": 0.7, "bloom": 0.15, "glow_thr": 0.8,
		"vfog_d": 0.012, "vfog_c": Color(0.7, 0.75, 0.9),
		"sun_rot": Vector3(-52, 140, 0), "sun_c": Color(0.55, 0.65, 0.95), "sun_e": 0.42, "sun_body": 1.0,   # 1 = 月亮
		"head": 6.0, "cabin": 3.0, "fire": 4.5, "fire_r": 7.0, "lantern": 2.5, "tent": 2.0, "bulbs": 3.0,
		"ff": 2.5, "head_glow": 3.5, "tail_glow": 2.0,
	},
}
var sun: DirectionalLight3D
var env: Environment
var sky_mat: ProceduralSkyMaterial
var fire_light: OmniLight3D
var cabin_light: OmniLight3D
var lantern_light: OmniLight3D
var tent_light: OmniLight3D
var headlights: Array[SpotLight3D] = []
var dust_mat: StandardMaterial3D
var night_mats := {}   # 材質名 → [StandardMaterial3D]，夜晚要開自發光的（車燈罩、尾燈）
const NIGHT_MATS := ["headlightGlass", "tailRed"]
var bench_t := 0.0
var bench_frames := 0
var bench_acc := 0.0

# 環繞鏡頭
var pivot: Node3D
var cam: Camera3D
var attrs: CameraAttributesPractical
var yaw := deg_to_rad(38.0)
var pitch := deg_to_rad(-33.0)
var dist := 72.0
var idle := 0.0
var dragging := false


func _ready() -> void:
	rng.seed = 11
	noise.seed = 5
	noise.frequency = 0.03
	noise.fractal_octaves = 3
	forest_noise.seed = 21
	forest_noise.frequency = 0.05
	forest_noise.fractal_octaves = 2
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--tree-dir="):
			tree_dir = arg.trim_prefix("--tree-dir=")
		elif arg == "--bench":
			bench = true
			DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
	var to_fire := FIRE - TENT
	tent_rot = atan2(to_fire.x, to_fire.y)   # 門（模型 +Z，Blender 的 -Y）朝向營火
	rug_center = TENT + to_fire.normalized() * 2.5
	_setup_env()
	_build_path_mask()
	_build_ground()
	_build_water()
	_build_grass()
	_build_forest()
	_build_understory()
	_build_props()
	_build_dust()
	_build_camera()
	_build_help()
	set_time(TimeOfDay.DAY, true)
	if OS.get_cmdline_user_args().size() > 0:
		# 截圖／錄影模式：視窗置頂並拉到前景。被別的視窗蓋住時 macOS 會把它標成 occluded，Godot 就停止繪製，
		# 之後 --write-movie 寫出來的每一張都是同一張。
		DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
		DisplayServer.window_move_to_foreground()
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--cam=") or arg.begins_with("--cam-rel="):
			# --cam-rel：y 是相對地面的高度（山丘上拍特寫不會埋進地裡）
			cam_locked = true
			var rel := arg.begins_with("--cam-rel=")
			var v := arg.split("=")[1].split_floats(",")
			if v.size() >= 6:
				var c := Camera3D.new()
				add_child(c)
				var y0 := h(v[0], v[2]) if rel else 0.0
				var y1 := h(v[3], v[5]) if rel else 0.0
				c.position = Vector3(v[0], v[1] + y0, v[2])
				c.look_at(Vector3(v[3], v[4] + y1, v[5]))
				c.fov = v[6] if v.size() > 6 else 28.0
				c.attributes = attrs
				c.current = true
		elif arg.begins_with("--ambient="):  # debug: 改用純色環境光
			env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
			env.ambient_light_color = Color(0.80, 0.86, 0.94)
			env.ambient_light_energy = float(arg.trim_prefix("--ambient="))
		elif arg == "--flat":  # debug: 關掉 SSAO/SSIL
			env.ssao_enabled = false
			env.ssil_enabled = false
		elif arg.begins_with("--ground-dbg="):
			var gm := (get_node("Ground") as MeshInstance3D).material_override as ShaderMaterial
			gm.set_shader_parameter("dbg", int(arg.trim_prefix("--ground-dbg=")))
		elif arg == "--ground-std":
			var sm := StandardMaterial3D.new()
			sm.albedo_color = Color(0.32, 0.54, 0.22)
			sm.roughness = 1.0
			(get_node("Ground") as MeshInstance3D).material_override = sm
		elif arg == "--night":
			set_time(TimeOfDay.NIGHT, true)
		elif arg == "--dusk":
			set_time(TimeOfDay.DUSK, true)
		elif arg == "--tod-debug":
			tod_debug = true
		elif arg == "--auto":
			auto_cycle = true
		elif arg.begins_with("--demo="):
			demo_len = float(arg.trim_prefix("--demo="))
			cam_locked = true
			auto_cycle = false
			if help_label:
				help_label.visible = false
		elif arg.begins_with("--tod-seek="):   # debug：把正在進行的漸變直接跳到第 t 秒（截圖用；接在 --to= 之後）
			tod_t = float(arg.trim_prefix("--tod-seek="))
			_tod_tick(0.0)
		elif arg.begins_with("--to="):   # debug：啟動後立刻開始 10 秒漸變到指定時段
			var name := arg.trim_prefix("--to=")
			set_time(TimeOfDay.NIGHT if name == "night" else (TimeOfDay.DUSK if name == "dusk" else TimeOfDay.DAY))
		elif arg == "--no-water":
			(get_node("Water") as MeshInstance3D).visible = false
		elif arg == "--no-glow":
			(get_node("WorldEnv") as WorldEnvironment).environment.glow_enabled = false
		elif arg == "--no-dof":
			attrs.dof_blur_far_enabled = false
			attrs.dof_blur_near_enabled = false
		elif arg == "--no-shadow":
			(get_node("Sun") as DirectionalLight3D).shadow_enabled = false
		elif arg.begins_with("--orbit="):
			cam_locked = true
			var v := arg.trim_prefix("--orbit=").split_floats(",")
			if v.size() == 3:
				yaw = deg_to_rad(v[0])
				pitch = deg_to_rad(v[1])
				dist = v[2]


# ---------------------------------------------------------------- terrain

func _g(p: Vector2, c: Vector2, s: float) -> float:
	return exp(-p.distance_squared_to(c) / (2.0 * s * s))


## 營地與露營車下方的平整墊：[中心, 全平半徑, 過渡半徑]
const PADS := [[CAMP, 4.5, 9.0], [VAN, 2.4, 5.5]]


func h(x: float, z: float) -> float:
	var y := _h_raw(x, z)
	for pad: Array in PADS:
		var c: Vector2 = pad[0]
		var d := Vector2(x, z).distance_to(c)
		if d < pad[2]:
			y = lerpf(_h_raw(c.x, c.y), y, smoothstep(pad[1], pad[2], d))
	return y


func _h_raw(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var pf := _g(p, POND, 7.0)
	var y := (noise.get_noise_2d(x, z) * 1.6 + noise.get_noise_2d(x * 4.0 + 900.0, z * 4.0) * 0.18) * (1.0 - pf)
	y += 5.5 * _g(p, HILL, 6.5)
	y -= 2.9 * _g(p, POND, 4.5)
	# 池塘外圍不得低於水面（避免水面露出池塘外），池塘內不設限
	var d := p.distance_to(POND)
	var floor_y := lerpf(-10.0, WATER_Y + 0.35, smoothstep(4.0, 7.5, d))
	return maxf(y, floor_y)


func path_mask(x: float, z: float) -> float:
	var px := clampi(int((x / SIZE + 0.5) * MASK_RES), 0, MASK_RES - 1)
	var py := clampi(int((z / SIZE + 0.5) * MASK_RES), 0, MASK_RES - 1)
	return path_img.get_pixel(px, py).r


func forest_density(x: float, z: float) -> float:
	var p := Vector2(x, z)
	var f := forest_noise.get_noise_2d(x, z) * 0.5 + 0.5
	var open := minf(smoothstep(6.5, 11.0, p.distance_to(POND)), smoothstep(4.0, 8.0, p.distance_to(CAMP)))
	open = minf(open, smoothstep(5.5, 9.5, p.distance_to(VAN)))
	return (0.35 + 0.65 * smoothstep(0.3, 0.6, f)) * open


func blocked(x: float, z: float, path_limit := 0.2) -> bool:
	var p := Vector2(x, z)
	return (path_mask(x, z) > path_limit or p.distance_to(POND) < 7.0 or p.distance_to(CAMP) < 4.5
		or p.distance_to(TENT) < 4.0 or p.distance_to(VAN) < 6.2 or p.distance_to(FIRE) < 2.6)


func _catmull(p0: Vector2, p1: Vector2, p2: Vector2, p3: Vector2, t: float) -> Vector2:
	var t2 := t * t
	var t3 := t2 * t
	return 0.5 * ((2.0 * p1) + (-p0 + p2) * t + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2 + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)


func _build_path_mask() -> void:
	var ctrl := PackedVector2Array([
		Vector2(-34, 12), Vector2(-24, 10), Vector2(-14, 6), Vector2(-4, 2), Vector2(4, -3),
		Vector2(12, -9), Vector2(20, -15), Vector2(30, -21), Vector2(40, -27)])
	for i in range(1, ctrl.size() - 2):
		for k in 24:
			path_pts.append(_catmull(ctrl[i - 1], ctrl[i], ctrl[i + 1], ctrl[i + 2], k / 24.0))
	path_img = Image.create_empty(MASK_RES, MASK_RES, false, Image.FORMAT_L8)
	var px_per_m := MASK_RES / SIZE
	var r := int(2.0 * px_per_m) + 1
	for pt in path_pts:
		var cx := (pt.x / SIZE + 0.5) * MASK_RES
		var cy := (pt.y / SIZE + 0.5) * MASK_RES
		for dy in range(-r, r + 1):
			for dx in range(-r, r + 1):
				var ix := int(cx) + dx
				var iy := int(cy) + dy
				if ix < 0 or iy < 0 or ix >= MASK_RES or iy >= MASK_RES:
					continue
				var d := Vector2(ix + 0.5 - cx, iy + 0.5 - cy).length() / r
				var v := 1.0 - smoothstep(0.45, 1.0, d)
				if v > path_img.get_pixel(ix, iy).r:
					path_img.set_pixel(ix, iy, Color(v, v, v))


func _ground_material() -> ShaderMaterial:
	var nt := NoiseTexture2D.new()
	var nn := FastNoiseLite.new()
	nn.seed = 8
	nn.frequency = 0.02
	nn.fractal_octaves = 3
	nt.noise = nn
	nt.seamless = true
	nt.width = 512
	nt.height = 512
	var sh := Shader.new()
	sh.code = GROUND_SHADER
	var mat := ShaderMaterial.new()
	mat.shader = sh
	mat.set_shader_parameter("noise_tex", nt)
	mat.set_shader_parameter("path_tex", ImageTexture.create_from_image(path_img))
	mat.set_shader_parameter("world_size", SIZE)
	mat.set_shader_parameter("water_y", WATER_Y)
	mat.set_shader_parameter("pond_center", POND)
	return mat


func _build_ground() -> void:
	var n := int(SIZE / STEP) + 1
	var half := SIZE * 0.5
	var hts := PackedFloat32Array()
	hts.resize(n * n)
	for j in n:
		for i in n:
			hts[j * n + i] = h(i * STEP - half, j * STEP - half)
	var verts := PackedVector3Array()
	var norms := PackedVector3Array()
	verts.resize(n * n)
	norms.resize(n * n)
	for j in n:
		for i in n:
			var k := j * n + i
			var sx := hts[j * n + mini(i + 1, n - 1)] - hts[j * n + maxi(i - 1, 0)]
			var sz := hts[mini(j + 1, n - 1) * n + i] - hts[maxi(j - 1, 0) * n + i]
			verts[k] = Vector3(i * STEP - half, hts[k], j * STEP - half)
			norms[k] = Vector3(-sx, 2.0 * STEP, -sz).normalized()
	var idx := PackedInt32Array()
	idx.resize((n - 1) * (n - 1) * 6)
	var c := 0
	for j in n - 1:
		for i in n - 1:
			var a := j * n + i
			idx[c] = a; idx[c + 1] = a + 1; idx[c + 2] = a + n
			idx[c + 3] = a + 1; idx[c + 4] = a + n + 1; idx[c + 5] = a + n
			c += 6
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = norms
	arrays[Mesh.ARRAY_INDEX] = idx
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := _ground_material()
	var mi := MeshInstance3D.new()
	mi.name = "Ground"
	mi.mesh = mesh
	mi.material_override = mat
	add_child(mi)

	# 地台側面（土層）與底面
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var edges := [
		[Vector3(0, 0, -1), func(i: int) -> int: return i],                       # z = -half
		[Vector3(1, 0, 0), func(i: int) -> int: return i * n + (n - 1)],          # x = +half
		[Vector3(0, 0, 1), func(i: int) -> int: return (n - 1) * n + (n - 1 - i)], # z = +half
		[Vector3(-1, 0, 0), func(i: int) -> int: return (n - 1 - i) * n],         # x = -half
	]
	for e: Array in edges:
		var nrm: Vector3 = e[0]
		var at: Callable = e[1]
		for i in n - 1:
			var a := verts[at.call(i)]
			var b := verts[at.call(i + 1)]
			var a0 := Vector3(a.x, BASE_Y, a.z)
			var b0 := Vector3(b.x, BASE_Y, b.z)
			for v: Vector3 in [a, b0, b, a, a0, b0]:
				st.set_normal(nrm)
				st.add_vertex(v)
	for v: Vector3 in [Vector3(-half, BASE_Y, -half), Vector3(half, BASE_Y, half), Vector3(half, BASE_Y, -half),
			Vector3(-half, BASE_Y, -half), Vector3(-half, BASE_Y, half), Vector3(half, BASE_Y, half)]:
		st.set_normal(Vector3.DOWN)
		st.add_vertex(v)
	var side := MeshInstance3D.new()
	side.name = "Sides"
	side.mesh = st.commit()
	side.material_override = mat
	add_child(side)


func _build_water() -> void:
	var pm := PlaneMesh.new()
	pm.size = Vector2(19, 19)
	pm.subdivide_width = 30
	pm.subdivide_depth = 30
	var sh := Shader.new()
	sh.code = WATER_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	var mi := MeshInstance3D.new()
	mi.name = "Water"
	mi.mesh = pm
	mi.material_override = m
	mi.position = Vector3(POND.x, WATER_Y, POND.y)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mi)


# ---------------------------------------------------------------- grass

func _grass_tuft() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for k in 3:
		var ang := k * PI / 3.0
		var dir := Vector3(cos(ang), 0, sin(ang))
		var lean := Vector3(-sin(ang), 0, cos(ang)) * 0.06
		var b0 := -dir * 0.07
		var b1 := dir * 0.07
		var t0 := -dir * 0.015 + Vector3.UP * 0.4 + lean
		var t1 := dir * 0.015 + Vector3.UP * 0.4 + lean
		for v: Array in [[b0, 0.0], [b1, 0.0], [t1, 1.0], [b0, 0.0], [t1, 1.0], [t0, 1.0]]:
			st.set_uv(Vector2(0.5, v[1]))
			st.set_normal(Vector3.UP)
			st.set_color(Color.WHITE)
			st.add_vertex(v[0])
	return st.commit()


func _build_grass() -> void:
	var sh := Shader.new()
	sh.code = GRASS_SHADER
	var mat := ShaderMaterial.new()
	mat.shader = sh
	var gm := (get_node("Ground") as MeshInstance3D).material_override as ShaderMaterial
	mat.set_shader_parameter("noise_tex", gm.get_shader_parameter("noise_tex"))
	var variants := ["gen/grass_tuft_A", "gen/grass_tuft_B", "gen/grass_tuft_C"]
	var xf: Array = [[], [], []]
	var cols: Array = [[], [], []]
	var half := SIZE * 0.5 - 0.4
	var spacing := 0.3
	var cells := int((half * 2.0) / spacing)
	var total := 0
	for j in cells:
		for i in cells:
			var x := -half + (i + rng.randf()) * spacing
			var z := -half + (j + rng.randf()) * spacing
			if path_mask(x, z) > 0.28 - rng.randf() * 0.15:
				continue
			var y := h(x, z)
			if y < WATER_Y + 0.35:
				continue
			if rng.randf() < 0.05:
				continue
			var pg := Vector2(x, z)
			if pg.distance_to(TENT) < 2.5 or pg.distance_to(VAN) < 2.7 or pg.distance_to(rug_center) < 1.1 or pg.distance_to(FIRE) < 0.75:
				continue
			var k := rng.randi() % 3
			var sc := rng.randf_range(0.9, 1.1)
			var basis := Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3(sc, sc * rng.randf_range(0.92, 1.08), sc))
			xf[k].append(Transform3D(basis, Vector3(x, y - 0.02, z)))
			var v := rng.randf_range(0.97, 1.03)   # 幾乎不做逐叢變色，變化交給地面的低頻色塊
			cols[k].append(Color(v, v, v))
			total += 1
	for k in 3:
		var km := kenney_mesh(variants[k])
		var mesh: ArrayMesh = km[0]
		mesh.surface_set_material(0, mat)
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = mesh
		mm.instance_count = xf[k].size()
		for i in xf[k].size():
			mm.set_instance_transform(i, xf[k][i] * km[1])
			mm.set_instance_color(i, cols[k][i])
		var mmi := MultiMeshInstance3D.new()
		mmi.name = "Grass_%d" % k
		mmi.multimesh = mm
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(mmi)
	print("DIORAMA grass=%d" % total)


# ---------------------------------------------------------------- Kenney models

func kenney_mesh(model_name: String) -> Array:
	## 回傳 [mesh(已換色), 模型內部的 transform]
	if _mesh_cache.has(model_name):
		return _mesh_cache[model_name]
	var path := ("res://assets/" + model_name + ".glb") if "/" in model_name else (NATURE + model_name + ".glb")
	var sc: Node3D = (load(path) as PackedScene).instantiate()
	var mi: MeshInstance3D = sc.find_children("*", "MeshInstance3D", true, false)[0]
	var mesh: ArrayMesh = mi.mesh.duplicate()
	for i in mesh.get_surface_count():
		var m := mesh.surface_get_material(i) as StandardMaterial3D
		if m == null:
			continue
		if m.resource_name in ["leafsGreen", "leafsDark"]:
			# 葉子：雙面、乘頂點色與實例色、隨風擺動
			if leaf_shader == null:
				leaf_shader = Shader.new()
				leaf_shader.code = LEAF_SHADER
			var lm := ShaderMaterial.new()
			lm.shader = leaf_shader
			lm.set_shader_parameter("albedo", PALETTE[m.resource_name])
			mesh.surface_set_material(i, lm)
			continue
		m = m.duplicate()
		if PALETTE.has(m.resource_name):
			m.albedo_color = PALETTE[m.resource_name]
		if m.resource_name in ["grass", "colorRed", "colorYellow", "colorPurple"]:
			m.cull_mode = BaseMaterial3D.CULL_DISABLED  # 單片花瓣／葉子要雙面
		m.vertex_color_use_as_albedo = true
		if PROP_MATS.has(m.resource_name):
			var pmv: Dictionary = PROP_MATS[m.resource_name]
			m.roughness = pmv.get("roughness", 0.6)
			m.metallic = pmv.get("metallic", 0.0)
			if pmv.has("albedo"):
				m.albedo_color = pmv["albedo"]
			if pmv.has("clearcoat"):
				m.clearcoat_enabled = true
				m.clearcoat = pmv["clearcoat"]
				m.clearcoat_roughness = 0.15
			if pmv.has("alpha"):
				m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
				m.albedo_color.a = pmv["alpha"]
				m.specular_mode = BaseMaterial3D.SPECULAR_SCHLICK_GGX
			if pmv.get("two_sided", false):
				m.cull_mode = BaseMaterial3D.CULL_DISABLED
			if pmv.has("specular"):
				m.metallic_specular = pmv["specular"]
			m.metallic_specular = 0.5
		elif not m.emission_enabled:
			m.roughness = 0.9
		if m.emission_enabled and m.resource_name in ["flameOrange", "flameYellow"]:
			# 火焰：換成會扭動的 shader（頂點隨時間擺動 + 自發光呼吸）
			if flame_shader == null:
				flame_shader = Shader.new()
				flame_shader.code = FLAME_SHADER
			var fm := ShaderMaterial.new()
			fm.shader = flame_shader
			fm.set_shader_parameter("albedo", m.emission)
			fm.set_shader_parameter("glow", m.emission_energy_multiplier)
			fm.set_shader_parameter("seed", 1.7 if m.resource_name == "flameYellow" else 0.0)
			fm.set_meta("base", m.emission_energy_multiplier)
			flame_mats.append(fm)
			mesh.surface_set_material(i, fm)
			continue
		if m.resource_name in NIGHT_MATS:
			if not night_mats.has(m.resource_name):
				night_mats[m.resource_name] = []
			night_mats[m.resource_name].append(m)
		mesh.surface_set_material(i, m)
	var result := [mesh, mi.transform]
	_mesh_cache[model_name] = result
	sc.free()
	return result


func place_multimesh(model_name: String, xf: Array[Transform3D], cols: Array[Color], shadows := true) -> void:
	if xf.is_empty():
		return
	var km := kenney_mesh(model_name)
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = km[0]
	mm.instance_count = xf.size()
	for i in xf.size():
		mm.set_instance_transform(i, xf[i] * km[1])
		mm.set_instance_color(i, cols[i])
	var mmi := MultiMeshInstance3D.new()
	mmi.name = model_name
	mmi.multimesh = mm
	if not shadows:
		mmi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(mmi)


func place_one(model_name: String, x: float, z: float, s: float, rot := 0.0, y_off := 0.0, y_abs := NAN) -> MeshInstance3D:
	var km := kenney_mesh(model_name)
	var mi := MeshInstance3D.new()
	mi.mesh = km[0]
	var y := h(x, z) + y_off if is_nan(y_abs) else y_abs
	mi.transform = Transform3D(Basis(Vector3.UP, rot).scaled(Vector3.ONE * s), Vector3(x, y, z)) * km[1]
	add_child(mi)
	return mi


func _xf(x: float, z: float, s: float, y_off := 0.0) -> Transform3D:
	return Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * s), Vector3(x, h(x, z) + y_off, z))


func _tint(v0 := 0.88, v1 := 1.1) -> Color:
	var v := rng.randf_range(v0, v1)
	return Color(v * rng.randf_range(0.90, 1.08), v, v * rng.randf_range(0.85, 1.05))


func _build_forest() -> void:
	# tools/gen_assets.py 用 Blender 生成的樹（assets/gen/）
	var kinds := {
		"tree_round_A": 0.14, "tree_round_B": 0.14, "tree_round_C": 0.14, "tree_round_D": 0.14,
		"tree_oak_A": 0.09, "tree_oak_B": 0.09, "tree_tall_A": 0.07, "tree_tall_B": 0.07,
		"tree_pine_A": 0.04, "tree_pine_B": 0.04, "tree_pine_C": 0.04,
	}
	var names: Array = kinds.keys()
	var xfs := {}
	var cols := {}
	for nm: String in names:
		xfs[nm] = [] as Array[Transform3D]
		cols[nm] = [] as Array[Color]
	var half := SIZE * 0.5 - 1.8
	var spacing := 2.5
	var cells := int((half * 2.0) / spacing)
	var count := 0
	for j in cells:
		for i in cells:
			var x := -half + (i + rng.randf()) * spacing
			var z := -half + (j + rng.randf()) * spacing
			if blocked(x, z, 0.08):
				continue
			if rng.randf() > forest_density(x, z) * 0.7:
				continue
			var r := rng.randf()
			var acc := 0.0
			var nm: String = names[0]
			for k: String in names:
				acc += kinds[k]
				if r <= acc:
					nm = k
					break
			xfs[nm].append(_xf(x, z, rng.randf_range(2.6, 3.6), -0.08))
			cols[nm].append(_tint(0.85, 1.12))
			count += 1
	for nm: String in names:
		place_multimesh(tree_dir + "/" + nm, xfs[nm], cols[nm])
	print("DIORAMA trees=%d (%s)" % [count, tree_dir])


func _scatter(model_name: String, count: int, s_min: float, s_max: float, y_off: float,
		want_forest: float, shadows := true) -> void:
	var xf: Array[Transform3D] = []
	var cols: Array[Color] = []
	var half := SIZE * 0.5 - 1.2
	var tries := 0
	while xf.size() < count and tries < count * 15:
		tries += 1
		var x := rng.randf_range(-half, half)
		var z := rng.randf_range(-half, half)
		if blocked(x, z):
			continue
		var f := forest_density(x, z)
		if want_forest > 0.0 and rng.randf() > f * want_forest:
			continue
		if want_forest < 0.0 and rng.randf() < f * -want_forest:
			continue
		xf.append(_xf(x, z, rng.randf_range(s_min, s_max), y_off))
		cols.append(_tint())
	place_multimesh(model_name, xf, cols, shadows)


func _build_understory() -> void:
	# 全部是 tools/gen_assets.py 產的（assets/gen/）
	_scatter("gen/bush_A", 60, 2.0, 3.0, -0.05, 1.2)
	_scatter("gen/bush_B", 50, 2.0, 3.0, -0.05, 1.2)
	_scatter("gen/bush_C", 40, 2.2, 3.2, -0.05, 1.4)
	_scatter("gen/fern_A", 90, 1.8, 2.6, -0.04, 1.6, false)
	_scatter("gen/fern_B", 70, 1.8, 2.6, -0.04, 1.6, false)
	_scatter("gen/pine_small", 40, 2.2, 3.2, -0.1, 1.6)
	_scatter("gen/mushroom_red", 50, 1.6, 2.4, -0.03, 1.8, false)
	_scatter("gen/mushroom_tan_group", 40, 1.6, 2.4, -0.03, 1.8, false)
	_scatter("gen/flower_yellow", 160, 2.0, 2.8, -0.03, -0.9, false)
	_scatter("gen/flower_purple", 90, 2.0, 2.8, -0.03, -0.9, false)
	_scatter("gen/flower_red", 70, 2.0, 2.8, -0.03, -0.9, false)
	_scatter("gen/rock_small_A", 30, 1.6, 2.8, -0.04, 0.0)
	_scatter("gen/rock_small_B", 30, 1.6, 2.8, -0.04, 0.0)
	_scatter("gen/rock_large_A", 14, 2.0, 3.0, -0.08, 0.0)
	_scatter("gen/rock_large_B", 12, 2.0, 3.0, -0.08, 0.0)
	_scatter("gen/log_A", 10, 2.0, 3.0, -0.02, 1.0)
	_scatter("gen/log_B", 8, 2.0, 3.0, -0.02, 1.0)
	_scatter("gen/stump_A", 12, 2.0, 2.8, -0.03, 1.0)
	_scatter("gen/stump_B", 8, 2.0, 2.8, -0.03, 1.0)


func _build_props() -> void:
	# 營地：Blender 生成的鐘形帳篷、露營車、露營器具（單位 = 公尺，scale 1）
	place_one("gen/dome_tent", TENT.x, TENT.y, 1.15, tent_rot, 0.0)
	var van := place_one("gen/camper_van", VAN.x, VAN.y, 1.0, VAN_ROT, 0.0)
	van.layers = 2   # 第 2 層：反射探針不拍它，鍍鉻與玻璃才不會反射到自己的車身
	cabin_light = OmniLight3D.new()   # 車內小暖光：透過玻璃看得到座椅與內裝
	cabin_light.position = Vector3(VAN.x, h(VAN.x, VAN.y) + 1.05, VAN.y) + Basis(Vector3.UP, VAN_ROT) * Vector3(0.25, 0.0, 0.0)
	cabin_light.light_color = Color(1.0, 0.88, 0.72)
	cabin_light.light_energy = 2.2
	cabin_light.omni_range = 2.4
	cabin_light.shadow_enabled = false
	add_child(cabin_light)
	# 車頭燈（夜晚才開）：模型 +X 是車頭，Blender 的 ±Y 進 Godot 是 ∓Z
	var van_base := Vector3(VAN.x, h(VAN.x, VAN.y), VAN.y)
	var van_fwd := Basis(Vector3.UP, VAN_ROT) * Vector3(1.0, 0.0, 0.0)
	for sz in [-1.0, 1.0]:
		var spot := SpotLight3D.new()
		spot.light_color = Color(1.0, 0.92, 0.72)
		spot.light_energy = 0.0
		spot.spot_range = 16.0
		spot.spot_angle = 30.0
		spot.spot_angle_attenuation = 0.7
		spot.light_volumetric_fog_energy = 2.5
		spot.shadow_enabled = true
		add_child(spot)
		spot.position = van_base + Basis(Vector3.UP, VAN_ROT) * Vector3(1.64, 0.83, sz * 0.46)
		spot.look_at(spot.position + van_fwd * 4.0 - Vector3(0.0, 0.5, 0.0), Vector3.UP)
		headlights.append(spot)
	place_one("gen/campfire", FIRE.x, FIRE.y, 1.0, 0.4, 0.0)
	place_one("gen/tripod_kettle", FIRE.x, FIRE.y, 1.0, 1.1, 0.0)
	var chairs := ["gen/camp_chair_blue", "gen/camp_chair_red", "gen/camp_chair_blue"]
	var offs := [Vector2(-1.7, 0.9), Vector2(0.7, 1.8), Vector2(1.9, -0.7)]
	for i in 3:
		var cp: Vector2 = FIRE + offs[i]
		var d: Vector2 = FIRE - cp
		place_one(chairs[i], cp.x, cp.y, 1.0, atan2(-d.y, d.x), 0.0)   # 椅子（模型 +X）面向營火
	place_one("gen/camp_table", TABLE.x, TABLE.y, 1.0, 0.35, 0.0)
	place_one("gen/lantern", TABLE.x + 0.28, TABLE.y - 0.12, 1.0, 0.0, 0.74)
	lantern_light = OmniLight3D.new()
	lantern_light.position = Vector3(TABLE.x + 0.28, h(TABLE.x + 0.28, TABLE.y - 0.12) + 1.0, TABLE.y - 0.12)
	lantern_light.light_color = Color(1.0, 0.82, 0.5)
	lantern_light.light_energy = 0.0
	lantern_light.omni_range = 5.0
	add_child(lantern_light)
	tent_light = OmniLight3D.new()   # 帳篷門口（雨棚下）的燈
	tent_light.position = Vector3(rug_center.x, h(rug_center.x, rug_center.y) + 1.1, rug_center.y)
	tent_light.light_color = Color(1.0, 0.85, 0.6)
	tent_light.light_energy = 0.0
	tent_light.omni_range = 5.5
	add_child(tent_light)
	place_one("gen/cooler", TABLE.x - 1.0, TABLE.y + 0.5, 1.0, 0.6, 0.0)
	place_one("gen/crate_A", VAN.x - 1.4, VAN.y - 3.2, 1.0, 0.2, 0.0)
	place_one("gen/crate_B", VAN.x - 0.6, VAN.y - 3.5, 1.0, -0.4, 0.0)
	place_one("log_stack", CAMP.x - 3.5, CAMP.y + 1.5, 2.4, 0.8, -0.02)
	# 串燈：帳篷頂 → 露營車車頂架
	var van_roof := Vector3(VAN.x, 1.94, VAN.y) + Basis(Vector3.UP, VAN_ROT) * Vector3(-0.78, 0.0, -0.48)
	_string_lights(Vector3(TENT.x, 2.0, TENT.y), van_roof, 22)
	# 反射探針：鍍鉻與玻璃反射周圍的樹，不再是死灰
	var probe := ReflectionProbe.new()
	probe.update_mode = ReflectionProbe.UPDATE_ONCE
	probe.size = Vector3(32, 14, 32)
	probe.position = Vector3(CAMP.x - 2.0, 4.0, CAMP.y + 3.0)
	probe.box_projection = true
	probe.cull_mask &= ~2
	probe.intensity = 0.7
	probe.ambient_mode = ReflectionProbe.AMBIENT_DISABLED   # 只給反射，不覆蓋環境光（否則探針一更新整個營地就變暗）
	probe.max_distance = 60.0
	add_child(probe)
	fire_light = OmniLight3D.new()
	fire_light.position = Vector3(FIRE.x, 0.6, FIRE.y)
	fire_light.light_color = Color(1.0, 0.6, 0.3)
	fire_light.light_energy = 1.6
	fire_light.omni_range = 4.5
	add_child(fire_light)
	place_one("sign", -17.5, 8.0, 2.2, -0.9, -0.02)
	# 池塘：獨木舟、睡蓮、岸邊蘆葦
	place_one("canoe", POND.x - 5.2, POND.y + 1.4, 2.6, 0.35, 0.0, WATER_Y - 0.05)
	place_one("canoe_paddle", POND.x - 4.6, POND.y - 0.6, 2.4, 1.0, 0.0, WATER_Y + 0.02)
	for k in 7:
		var ang := k * TAU / 7.0 + 0.4
		var rr := rng.randf_range(1.5, 3.4)
		place_one("lily_large" if k % 2 == 0 else "lily_small", POND.x + cos(ang) * rr, POND.y + sin(ang) * rr,
				2.2, rng.randf() * TAU, 0.0, WATER_Y + 0.02)
	for k in 10:
		var ang := k * TAU / 10.0
		var rr := 5.6 + rng.randf_range(-0.4, 0.5)
		var x := POND.x + cos(ang) * rr
		var z := POND.y + sin(ang) * rr
		if h(x, z) > WATER_Y + 0.15:
			place_one("gen/fern_A", x, z, 2.0, rng.randf() * TAU, -0.04)
	# 池邊大石
	place_one("gen/rock_large_A", POND.x + 5.4, POND.y + 4.6, 2.8, 0.7, -0.1)
	place_one("gen/rock_large_B", POND.x - 3.8, POND.y - 4.9, 2.2, 1.9, -0.06)


func _string_lights(a: Vector3, b: Vector3, bulbs: int) -> void:
	var rope_mat := StandardMaterial3D.new()
	rope_mat.albedo_color = Color(0.25, 0.22, 0.2)
	var bulb_mats: Array[StandardMaterial3D] = []
	for c: Color in [Color(1.0, 0.85, 0.5), Color(1.0, 0.6, 0.55), Color(0.7, 0.9, 1.0), Color(0.8, 1.0, 0.7)]:
		var bm := StandardMaterial3D.new()
		bm.albedo_color = c
		bm.emission_enabled = true
		bm.emission = c
		bm.emission_energy_multiplier = 2.5
		bulb_mats.append(bm)
	var sag := a.distance_to(b) * 0.03
	var segs := bulbs * 2
	var prev := a
	for i in range(1, segs + 1):
		var t := float(i) / segs
		var p := a.lerp(b, t) - Vector3(0, sag * 4.0 * t * (1.0 - t), 0)
		var seg := MeshInstance3D.new()
		var cm := CylinderMesh.new()
		cm.top_radius = 0.012
		cm.bottom_radius = 0.012
		cm.height = prev.distance_to(p)
		cm.radial_segments = 5
		seg.mesh = cm
		seg.material_override = rope_mat
		seg.position = (prev + p) * 0.5
		var dir := (p - prev).normalized()
		seg.basis = Basis(dir.cross(Vector3.RIGHT if absf(dir.y) > 0.9 else Vector3.UP).normalized().cross(dir), dir, dir.cross(Vector3.RIGHT if absf(dir.y) > 0.9 else Vector3.UP).normalized())
		add_child(seg)
		if i % 2 == 0:
			var bulb := MeshInstance3D.new()
			var sm := SphereMesh.new()
			sm.radius = 0.07
			sm.height = 0.14
			sm.radial_segments = 8
			sm.rings = 4
			bulb.mesh = sm
			var bmat: StandardMaterial3D = bulb_mats[(i / 2) % bulb_mats.size()].duplicate()
			bulb_mats_all.append(bmat)
			bulb.material_override = bmat
			bulb.position = p - Vector3(0, 0.09, 0)
			add_child(bulb)
		prev = p


# ---------------------------------------------------------------- atmosphere

func _setup_env() -> void:
	# 背景：柔和的淡藍灰漸層（用天空畫，環境光才有來源）
	sky_mat = ProceduralSkyMaterial.new()
	sky_mat.sky_top_color = Color(0.66, 0.80, 0.98)
	sky_mat.sky_horizon_color = Color(0.88, 0.92, 0.97)
	sky_mat.ground_horizon_color = Color(0.86, 0.88, 0.88)
	sky_mat.ground_bottom_color = Color(0.60, 0.62, 0.60)
	sky_mat.sky_curve = 0.2
	sky_mat.sun_angle_max = 0.0
	sky_mat.energy_multiplier = 1.35
	var sky := Sky.new()
	sky.sky_material = sky_mat
	env = Environment.new()
	env.background_mode = Environment.BG_SKY  # 環境光要靠天空，背景顏色就用天空畫
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.ambient_light_sky_contribution = 1.0
	env.ambient_light_energy = 0.24
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	env.tonemap_exposure = 0.74
	env.ssao_enabled = true
	env.ssao_radius = 1.5
	env.ssao_intensity = 1.5
	env.ssil_enabled = true
	env.ssil_intensity = 1.0
	env.glow_enabled = true
	env.glow_intensity = 0.2
	env.glow_bloom = 0.02
	env.glow_hdr_threshold = 1.4
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.18
	env.adjustment_saturation = 1.14
	var we := WorldEnvironment.new()
	we.name = "WorldEnv"
	we.environment = env
	add_child(we)

	sun = DirectionalLight3D.new()
	sun.name = "Sun"
	sun.rotation_degrees = Vector3(-44, 32, 0)
	sun.light_color = Color(1.0, 0.95, 0.85)
	sun.light_energy = 1.3
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_2_SPLITS
	sun.directional_shadow_max_distance = 130.0
	sun.directional_shadow_split_1 = 0.35
	sun.shadow_blur = 2.4
	sun.shadow_bias = 0.05
	sun.shadow_normal_bias = 3.5
	add_child(sun)


func _build_dust() -> void:
	var fx := CPUParticles3D.new()
	fx.amount = 220
	fx.lifetime = 10.0
	fx.preprocess = 10.0
	fx.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	fx.emission_box_extents = Vector3(20, 4, 20)
	fx.position = Vector3(0, 4, 0)
	fx.direction = Vector3(0.3, 0.1, 0.2)
	fx.spread = 180.0
	fx.gravity = Vector3.ZERO
	fx.initial_velocity_min = 0.05
	fx.initial_velocity_max = 0.25
	var q := QuadMesh.new()
	q.size = Vector2(0.035, 0.035)
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.albedo_color = Color(1.0, 0.95, 0.8, 0.28)
	m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	q.material = m
	fx.mesh = q
	add_child(fx)
	dust_mat = m


# ---------------------------------------------------------------- camera

func _build_camera() -> void:
	pivot = Node3D.new()
	pivot.position = Vector3(0, 0.5, 0)
	add_child(pivot)
	cam = Camera3D.new()
	cam.fov = 26.0
	attrs = CameraAttributesPractical.new()
	attrs.dof_blur_far_enabled = true
	attrs.dof_blur_near_enabled = true
	attrs.dof_blur_amount = 0.06
	cam.attributes = attrs
	pivot.add_child(cam)
	cam.current = true
	_apply_camera()


func _apply_camera() -> void:
	pivot.rotation = Vector3(pitch, yaw, 0)
	cam.position = Vector3(0, 0, dist)
	attrs.dof_blur_far_distance = dist + 8.0
	attrs.dof_blur_far_transition = dist * 0.45
	attrs.dof_blur_near_distance = dist - 14.0
	attrs.dof_blur_near_transition = dist * 0.25


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.is_pressed() and not event.is_echo():
		var kc := (event as InputEventKey).keycode
		if kc == KEY_N:
			auto_cycle = false
			set_time((tod + 1) % 3)
			return
		if kc == KEY_A:
			auto_cycle = not auto_cycle
			auto_timer = 0.0
			return
	if cam_locked:
		return
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			dragging = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			dist = maxf(34.0, dist * 0.92)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			dist = minf(120.0, dist / 0.92)
		idle = 0.0
	elif event is InputEventMouseMotion and dragging:
		var mm := event as InputEventMouseMotion
		yaw -= mm.relative.x * 0.006
		pitch = clampf(pitch - mm.relative.y * 0.005, deg_to_rad(-70.0), deg_to_rad(-8.0))
		idle = 0.0


func _process(delta: float) -> void:
	_demo_tick(delta)
	_tod_tick(delta)
	if auto_cycle and not tod_active:
		auto_timer += delta
		if auto_timer >= AUTO_HOLD:
			auto_timer = 0.0
			set_time((tod + 1) % 3)
	_flicker()
	if cam_locked:
		idle = 0.0
	if bench:
		bench_t += delta
		if bench_t > 2.0:
			bench_frames += 1
			bench_acc += delta
		if bench_t > 6.0:
			print("BENCH %s fps=%.1f  (%.2f ms/frame)" % [tree_dir, bench_frames / bench_acc, 1000.0 * bench_acc / bench_frames])
			get_tree().quit()
	idle += delta
	if idle > 4.0:
		yaw += delta * 0.05
	_apply_camera()


func set_time(t: int, instant := false) -> void:
	tod = t
	night = t == TimeOfDay.NIGHT
	var target: Dictionary = TOD_PRESETS[t]
	if instant or tod_cur.is_empty():
		tod_cur = target.duplicate()
		tod_active = false
		_apply_state(tod_cur)
	else:
		tod_from = tod_cur.duplicate()
		tod_to = target
		tod_t = 0.0
		tod_active = true


func set_night(on: bool) -> void:
	set_time(TimeOfDay.NIGHT if on else TimeOfDay.DAY)


func _tod_tick(delta: float) -> void:
	if not tod_active:
		return
	tod_t += delta
	var k := clampf(tod_t / tod_duration, 0.0, 1.0)
	if tod_debug and Engine.get_process_frames() % 30 == 0:
		var sr: Vector3 = tod_cur.get("sun_rot", Vector3.ZERO)
		print("TOD %d->%d t=%.1f k=%.2f sun_elev=%.0f az=%.0f sun_e=%.2f head=%.2f" % [tod_from.get("sun_body", 0), tod_to.get("sun_body", 0), tod_t, k, -sr.x, sr.y, tod_cur.get("sun_e", -1.0), tod_cur.get("head", -1.0)])
	var ks := k * k * (3.0 - 2.0 * k)   # smoothstep：頭尾慢、中間快
	tod_cur = _lerp_state(tod_from, tod_to, ks)
	_apply_state(tod_cur)
	if k >= 1.0:
		tod_active = false


func _lerp_state(a: Dictionary, b: Dictionary, k: float) -> Dictionary:
	var out := {}
	for key: String in b:
		var va = a[key]
		var vb = b[key]
		if va is float:
			out[key] = lerpf(va, vb, k)
		elif va is Color:
			out[key] = (va as Color).lerp(vb, k)
		elif va is Vector3:
			out[key] = (va as Vector3).lerp(vb, k)
		else:
			out[key] = vb
	# 太陽 ↔ 月亮換手：不直接在天上滑過去，而是先落到地平線下、再從另一邊升起
	if roundf(a.get("sun_body", 0.0)) != roundf(b.get("sun_body", 0.0)):
		var ra: Vector3 = a["sun_rot"]
		var rb: Vector3 = b["sun_rot"]
		if k < 0.5:
			var u := k * 2.0
			out["sun_rot"] = Vector3(lerpf(ra.x, 12.0, u), ra.y + 25.0 * u, 0.0)        # x 越大越低，>0 = 地平線下
			out["sun_c"] = a["sun_c"]
			out["sun_e"] = a["sun_e"] * clampf(1.0 - u * 1.6, 0.0, 1.0)                  # 碰到地平線就熄
			out["sun_disc"] = a["sun_disc"]
		else:
			var u := (k - 0.5) * 2.0
			out["sun_rot"] = Vector3(lerpf(12.0, rb.x, u), rb.y - 25.0 * (1.0 - u), 0.0)
			out["sun_c"] = b["sun_c"]
			out["sun_e"] = b["sun_e"] * clampf((u - 0.375) * 1.6, 0.0, 1.0)
			out["sun_disc"] = b["sun_disc"]
		# 暮光：兩個光源都在地平線下時，天空散射還在——環境光補一段、地平線留一抹餘暉，才不會整個黑掉
		var tw := pow(sin(PI * k), 0.6)   # 撐得久一點，月亮還沒升起前不會比深夜還黑
		out["amb_e"] = out["amb_e"] + 0.7 * tw
		out["amb_c"] = (out["amb_c"] as Color).lerp(Color(0.55, 0.50, 0.78), 0.6 * tw)
		out["sky_h"] = (out["sky_h"] as Color).lerp(Color(0.95, 0.55, 0.42), 0.55 * tw)
		out["sky_e"] = out["sky_e"] + 0.3 * tw
		out["exposure"] = out["exposure"] + 0.12 * tw
	return out


func _demo_tick(delta: float) -> void:
	if demo_len <= 0.0:
		return
	demo_t += delta
	var T := demo_t
	# 時段：0–5 白天 → 5–13 轉黃昏 → 13–17 黃昏 → 17–25 轉夜 → 25–30 夜
	if not demo_dusk_started and T >= demo_len * 0.17:
		demo_dusk_started = true
		tod_duration = demo_len * 0.27
		set_time(TimeOfDay.DUSK)
	if not demo_night_started and T >= demo_len * 0.57:
		demo_night_started = true
		tod_duration = demo_len * 0.27
		set_time(TimeOfDay.NIGHT)
	# 鏡頭：廣角慢繞 → 推進到營地 → 低角度環繞營火
	var u := clampf(T / demo_len, 0.0, 1.0)
	var push := smoothstep(demo_len * 0.40, demo_len * 0.80, T)
	yaw = deg_to_rad(20.0 + 80.0 * u)
	pitch = deg_to_rad(lerpf(-33.0, -21.0, push))
	dist = lerpf(72.0, 33.0, push)
	pivot.position = Vector3(0.0, 0.5, 0.0).lerp(Vector3(-7.0, 1.2, 0.0), push)
	if T > demo_len + 0.3:
		get_tree().quit()


func _flicker() -> void:
	if tod_cur.is_empty():
		return
	var t := Time.get_ticks_msec() * 0.001
	# 營火：幾個不成比例的正弦疊起來，像火在呼吸
	var fl := 1.0 + 0.16 * sin(t * 7.3) + 0.11 * sin(t * 12.7 + 1.3) + 0.07 * sin(t * 23.1 + 2.1)
	fire_light.light_energy = tod_cur["fire"] * fl
	for fm in flame_mats:
		fm.set_shader_parameter("glow", fm.get_meta("base") * (0.75 + 0.5 * (fl - 0.66)))
	lantern_light.light_energy = tod_cur["lantern"] * (1.0 + 0.06 * sin(t * 9.1) + 0.03 * sin(t * 17.3))
	# 串燈：每顆不同相位，慢慢呼吸
	var base: float = tod_cur["bulbs"]
	for i in bulb_mats_all.size():
		bulb_mats_all[i].emission_energy_multiplier = base * (1.0 + 0.18 * sin(t * 2.1 + i * 1.7) + 0.08 * sin(t * 5.3 + i * 0.9))


func _apply_state(st: Dictionary) -> void:
	sky_mat.sky_top_color = st["sky_top"]
	sky_mat.sky_horizon_color = st["sky_h"]
	sky_mat.ground_horizon_color = st["gnd_h"]
	sky_mat.ground_bottom_color = st["gnd_b"]
	sky_mat.energy_multiplier = st["sky_e"]
	sky_mat.sun_angle_max = st["sun_disc"]   # >0 才畫太陽圓盤（黃昏），跟著 DirectionalLight 方向
	sky_mat.sun_curve = 0.15
	# 環境光一律用純色（三個時段才能平滑插值；黃昏也才不會被橘紅天際染紅）
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = st["amb_c"]
	env.ambient_light_energy = st["amb_e"]
	env.tonemap_exposure = st["exposure"]
	env.glow_intensity = st["glow_i"]
	env.glow_bloom = st["bloom"]
	env.glow_hdr_threshold = st["glow_thr"]
	env.volumetric_fog_enabled = st["vfog_d"] > 0.0002
	env.volumetric_fog_density = st["vfog_d"]
	env.volumetric_fog_albedo = st["vfog_c"]
	env.volumetric_fog_ambient_inject = 0.02
	env.volumetric_fog_length = 80.0
	sun.rotation_degrees = st["sun_rot"]
	sun.light_color = st["sun_c"]
	sun.light_energy = st["sun_e"]
	for sp in headlights:
		sp.light_energy = st["head"]
	cabin_light.light_energy = st["cabin"]
	fire_light.light_energy = st["fire"]
	fire_light.omni_range = st["fire_r"]
	lantern_light.light_energy = st["lantern"]
	tent_light.light_energy = st["tent"]
	# 塵埃 ↔ 螢火蟲
	var ff: float = st["ff"]
	var fk := clampf(ff / 2.5, 0.0, 1.0)
	dust_mat.albedo_color = Color(1.0, 0.95, 0.8, 0.28).lerp(Color(0.75, 1.0, 0.45, 0.9), fk)
	dust_mat.emission_enabled = ff > 0.02
	dust_mat.emission = Color(0.6, 1.0, 0.3)
	dust_mat.emission_energy_multiplier = ff
	# 車燈罩、尾燈自發光
	for nm: String in NIGHT_MATS:
		var e: float = st["head_glow"] if nm == "headlightGlass" else st["tail_glow"]
		for m: StandardMaterial3D in night_mats.get(nm, []):
			m.emission_enabled = e > 0.02
			m.emission = Color(1.0, 0.9, 0.7) if nm == "headlightGlass" else Color(1.0, 0.2, 0.15)
			m.emission_energy_multiplier = e


func _build_help() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var font := SystemFont.new()
	font.font_names = PackedStringArray(["PingFang TC", "Heiti TC", "Noto Sans CJK TC", "sans-serif"])
	var l := Label.new()
	l.text = "拖曳旋轉　滾輪縮放　N 日／黃昏／夜（10 秒漸變）　A 自動循環"
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", 14)
	l.add_theme_color_override("font_color", Color(0.3, 0.35, 0.4, 0.7))
	l.anchor_top = 1.0
	l.anchor_bottom = 1.0
	l.offset_left = 16
	l.offset_top = -34
	layer.add_child(l)
	help_label = l
	if demo_len > 0.0:
		help_label.visible = false
