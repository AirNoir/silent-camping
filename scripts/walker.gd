extends CharacterBody3D
## 散步模式的 Q 版露營者（forest.gd 按 P 建立）。
## WASD／方向鍵相對鏡頭方向走、Shift 跑。高度直接跟地形函式（不靠物理地板），
## move_and_slide 只負責跟道具（StaticBody3D）的水平碰撞。
## 走路是程序動畫（scripts/rig.gd）：腳真的踩住地面不滑——每隻腳在「落後髖部半步」時才抬起、
## 落到預測的下一步位置；膝蓋由兩段式 IK 決定；骨盆隨步伐起伏、側移、扭轉，肩膀反向，手臂跟對側腳同步擺。
## 曠野之息式的「活著」細節：跑步有騰空段與前傾、手肘收起來擺；每一步落地身體往下沉一下、跑步還會踢起塵土；
## 支撐腳滑過髖部後踮腳跟推離；頭會看向鏡頭指的方向（玩家轉鏡頭、角色跟著看過去）；
## play_pick() 是彎腰伸手的採集動作（森林的小任務按 E 時呼叫）。

const RigScript := preload("res://scripts/rig.gd")
const WALK := 1.15
const RUN := 3.0
const ACCEL := 10.0
const TURN := 9.0
const ANKLE_H := 0.09

var ground: Callable            # (x, z) -> 地面高度
var cam_yaw: Callable           # () -> 鏡頭 yaw，輸入方向以它為準
var cam_fwd := Callable()       # () -> 鏡頭前方的水平角（與 face 同一套：atan2(-z, x)），頭會看過去
var bounds := 21.0
var water_y := -1.5
var auto_input := Vector2.ZERO  # debug／測試：固定輸入（x 右、y 後）
var auto_run := false

var model: Node3D
var rig
var feet: Array[Dictionary] = []   # 0 = 左、1 = 右：{pos(世界), from, to, swing, t, dur}
var gait := 0.0
var speed := 0.0
var face := 0.0
var idle_t := 0.0
var lean := 0.0
var look := 0.0
var look_target := 0.0
var look_timer := 0.0
var prev_hv := Vector3.ZERO
var stride := 0.36
var land_k := 0.0               # 落地下沉量：footfall 設 1、快速衰減，身體跟著彈一下
var act_t := 0.0                # 採集動作剩餘秒數（play_pick）
var act_pos := Vector3.ZERO
var dust: Array[CPUParticles3D] = []
var dust_i := 0


func setup(scene: Node3D) -> void:
	model = scene
	add_child(model)
	var sk: Skeleton3D = model.find_children("*", "Skeleton3D", true, false)[0]
	var face_mat: StandardMaterial3D = null
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if m and m.resource_name.begins_with("face"):
				face_mat = m
	rig = RigScript.new(sk, face_mat)
	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.20
	cap.height = 0.85
	col.shape = cap
	col.position.y = 0.47
	add_child(col)
	motion_mode = CharacterBody3D.MOTION_MODE_FLOATING   # 高度自己管，不要物理重力與地板判定
	model.rotation.y = face
	for i in 2:
		feet.append({"pos": Vector3.ZERO, "from": Vector3.ZERO, "to": Vector3.ZERO, "swing": false, "t": 0.0, "dur": 0.25})
	reset_feet()
	# 腳落地的塵土（跑步才有）：一小撮往上冒、散開就淡掉的沙色點
	for i in 3:
		var fx := CPUParticles3D.new()
		fx.one_shot = true
		fx.emitting = false
		fx.amount = 6
		fx.lifetime = 0.5
		fx.explosiveness = 1.0
		fx.direction = Vector3.UP
		fx.spread = 50.0
		fx.gravity = Vector3(0.0, -1.2, 0.0)
		fx.initial_velocity_min = 0.3
		fx.initial_velocity_max = 0.7
		var sc_c := Curve.new()
		sc_c.add_point(Vector2(0.0, 0.5))
		sc_c.add_point(Vector2(1.0, 1.5))
		fx.scale_amount_curve = sc_c
		var grad := Gradient.new()
		grad.set_color(0, Color(0.83, 0.77, 0.62, 0.55))
		grad.set_color(1, Color(0.83, 0.77, 0.62, 0.0))
		fx.color_ramp = grad
		var q := QuadMesh.new()
		q.size = Vector2(0.07, 0.07)
		var m := StandardMaterial3D.new()
		m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		m.vertex_color_use_as_albedo = true
		m.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
		q.material = m
		fx.mesh = q
		fx.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		add_child(fx)
		dust.append(fx)


func reset_feet() -> void:
	## 出生／瞬移後把腳放回髖部正下方
	for i in 2:
		feet[i]["pos"] = _rest_foot_world(i)
		feet[i]["swing"] = false


func play_pick(p: Vector3) -> void:
	## 採集：0.6 秒彎腰、右手伸向 p（世界座標）再收回
	act_t = 0.6
	act_pos = p


func _rest_foot_world(i: int) -> Vector3:
	var a: Vector3 = rig.rest_ankle("l" if i == 0 else "r")
	var w: Vector3 = model.global_transform * Vector3(a.x, 0.0, a.z)
	w.y = ground.call(w.x, w.z) + ANKLE_H
	return w


func _physics_process(delta: float) -> void:
	var inp := auto_input
	if inp == Vector2.ZERO:
		inp = Vector2(_key(KEY_D, KEY_RIGHT) - _key(KEY_A, KEY_LEFT), _key(KEY_S, KEY_DOWN) - _key(KEY_W, KEY_UP))
	var running := auto_run or Input.is_physical_key_pressed(KEY_SHIFT)
	var yaw: float = cam_yaw.call()
	var dir := Basis(Vector3.UP, yaw) * Vector3(inp.x, 0.0, inp.y)
	if dir.length() > 1.0:
		dir = dir.normalized()
	var target := dir * (RUN if running else WALK)
	velocity.x = move_toward(velocity.x, target.x, ACCEL * delta)
	velocity.z = move_toward(velocity.z, target.z, ACCEL * delta)
	velocity.y = 0.0
	move_and_slide()
	position.x = clampf(position.x, -bounds, bounds)
	position.z = clampf(position.z, -bounds, bounds)
	position.y = maxf(ground.call(position.x, position.z), water_y - 0.22)   # 池塘：涉水到小腿
	_animate(delta)


func _key(a: Key, b: Key) -> float:
	return 1.0 if (Input.is_physical_key_pressed(a) or Input.is_physical_key_pressed(b)) else 0.0


func _animate(delta: float) -> void:
	var hv := Vector3(velocity.x, 0.0, velocity.z)
	speed = hv.length()
	var moving := speed > 0.12
	gait = move_toward(gait, 1.0 if moving else 0.0, 5.0 * delta)
	var k := clampf(speed / RUN, 0.0, 1.0)
	idle_t += delta
	land_k = move_toward(land_k, 0.0, 7.0 * delta)
	# 面向：往速度方向轉；轉彎時往內側傾
	if moving:
		var want := atan2(-hv.z, hv.x)
		var dyaw := wrapf(want - face, -PI, PI)
		face = lerp_angle(face, want, TURN * delta)
		lean = lerpf(lean, clampf(-dyaw * 0.6, -0.25, 0.25) * k, 6.0 * delta)
	else:
		lean = lerpf(lean, 0.0, 6.0 * delta)
	model.rotation.y = face
	var heading := Vector3(cos(face), 0.0, -sin(face))
	var side_w := Vector3(-heading.z, 0.0, heading.x)   # 身體右側（+Z 在模型空間）
	stride = 0.17 + 0.085 * speed   # 三頭身的短腿：步幅跟著腿長縮
	var accel := (hv - prev_hv) / maxf(delta, 1e-4)
	prev_hv = hv
	# ---- 腳步：落後髖部半步就抬腳，落到預測位置；走路一次一隻腳、跑步允許短暫雙腳離地（騰空段）
	var swing_dur := clampf(0.5 * stride / maxf(speed, 0.4), 0.11, 0.28)
	for i in 2:
		var f := feet[i]
		var o := feet[1 - i]
		var hip_w: Vector3 = model.global_transform * Vector3(0.0, 0.0, rig.rest_hip("l" if i == 0 else "r").z)
		if not f["swing"]:
			var other_ok: bool = (not o["swing"]) or (k > 0.5 and (o["t"] as float) > 0.55)
			if moving and other_ok:
				var behind: float = (hip_w - f["pos"]).dot(heading)
				var lateral: float = absf((hip_w - f["pos"]).dot(side_w))
				if behind > stride * 0.5 or lateral > 0.17:
					_start_swing(i, hip_w + heading * (stride * 0.5 + speed * swing_dur * 0.9), swing_dur)
			elif not moving and not o["swing"]:
				var home := _rest_foot_world(i)
				if (f["pos"] - home).length() > 0.05:
					_start_swing(i, home, 0.22)
		if f["swing"]:
			f["t"] = minf(f["t"] + delta / f["dur"], 1.0)
			var t: float = f["t"]
			var ts := t * t * (3.0 - 2.0 * t)
			var p: Vector3 = (f["from"] as Vector3).lerp(f["to"], ts)
			p.y += (0.035 + 0.06 * k) * sin(PI * t)
			f["pos"] = p
			if t >= 1.0:
				f["swing"] = false
				f["pos"] = f["to"]
				_footfall(i, k)
	# ---- 骨盆：支撐腳那一側墊高、往支撐腳側移、往擺動腿方向扭；跑步起伏更大、前傾；落地往下沉一下
	var swing_i := -1
	var st := 0.0
	for i in 2:
		if feet[i]["swing"]:
			swing_i = i
			st = feet[i]["t"]
	var bob := ((0.022 + 0.04 * k) * gait * sin(PI * st)) if swing_i >= 0 else 0.0
	var sway := (0.018 * gait * sin(PI * st) * (1.0 if swing_i == 0 else -1.0)) if swing_i >= 0 else 0.0   # 擺左腳 → 重心往右(+Z)
	var hip_yaw := (0.10 * gait * sin(PI * st) * (-1.0 if swing_i == 0 else 1.0)) if swing_i >= 0 else 0.0   # 擺左腳 → 左髖往前 = 繞 +Y 負轉
	var pitch := (0.05 + 0.09 * k) * k * gait + clampf(accel.dot(heading) * 0.035, -0.14, 0.14)
	# 採集動作：彎腰（頭也低下來看目標）、右手伸過去
	var act_k := 0.0
	if act_t > 0.0:
		act_t -= delta
		act_k = sin(PI * clampf(1.0 - act_t / 0.6, 0.0, 1.0))
		pitch += 0.38 * act_k
	var inv := model.global_transform.affine_inverse()
	# 站姿髖高 0.385（rest 0.40）：膝蓋常保一點彎，腿才不會鎖直
	var hips := Vector3(0.0, 0.385 - 0.01 * gait - 0.018 * land_k * (0.3 + 0.7 * k) + bob - 0.08 * act_k, sway)
	# 閒置：慢慢換重心、呼吸、東張西望
	var breathe := 0.015 * sin(idle_t * 1.6)
	look_timer -= delta
	if look_timer <= 0.0:
		look_timer = randf_range(2.5, 5.0)
		look_target = randf_range(-0.5, 0.5)
	# 頭看向鏡頭指的方向（BotW：玩家轉鏡頭，角色跟著看過去）；走動時收斂回前方、跑步只偷瞄一點
	var cam_look := 0.0
	if cam_fwd.is_valid():
		var cdiff := wrapf((cam_fwd.call() as float) - face, -PI, PI)
		if absf(cdiff) < 2.0:
			cam_look = clampf(cdiff, -1.0, 1.0)
	look = lerpf(look, look_target * (1.0 - gait) + cam_look * (0.55 - 0.32 * gait), 2.5 * delta)
	var idle_sway := 0.012 * (1.0 - gait) * sin(idle_t * 0.7)
	hips.z += idle_sway
	rig.torso(hips, hip_yaw, pitch + breathe * 0.5, lean * 0.3 + idle_sway * 1.5,
		-hip_yaw * 0.7, breathe, look - hip_yaw * 0.3, 0.04 * k * gait + 0.02 * sin(idle_t * 0.9) + 0.25 * act_k, -lean * 0.4)
	# ---- 腿：腳踝目標 = 腳的世界位置轉回模型空間；擺動時腳尖下垂、支撐腳滑過髖部就踮腳跟推離
	for i in 2:
		var s := "l" if i == 0 else "r"
		var a_local: Vector3 = inv * (feet[i]["pos"] as Vector3)
		var toe_pitch := -0.5 * sin(PI * (feet[i]["t"] as float)) if feet[i]["swing"] else 0.0
		if not feet[i]["swing"] and moving:
			var hip_w: Vector3 = model.global_transform * Vector3(0.0, 0.0, rig.rest_hip(s).z)
			var push := clampf(((hip_w - (feet[i]["pos"] as Vector3)).dot(heading) / maxf(stride, 0.1) - 0.25) * 1.1, 0.0, 0.5) * gait
			a_local.y += push * 0.06
			toe_pitch = -push * 0.9
		var fdir := Basis(Vector3.BACK, toe_pitch) * Vector3.RIGHT
		rig.leg(s, a_local, fdir, Vector3.RIGHT)
	# ---- 手臂：跟對側腳同步（腳在前 → 同側手在後）；跑步手肘收起來用抽的擺（BotW 跑姿），閒置時微微晃
	for i in 2:
		var s := "l" if i == 0 else "r"
		var hip_w: Vector3 = model.global_transform * Vector3(0.0, 0.0, rig.rest_hip(s).z)
		var fwd: float = clampf(((feet[i]["pos"] as Vector3) - hip_w).dot(heading) / maxf(stride, 0.1), -0.6, 0.6)
		var swing := -fwd * (0.8 + 1.1 * k) * gait + 0.03 * (1.0 - gait) * sin(idle_t * 1.3 + float(i) * 2.1)
		var bend := 0.06 + 0.10 * maxf(swing, 0.0) + 0.40 * k * k
		rig.arm(s, rig.hang_arm_target(s, swing, bend), Vector3(-1.0, -0.3, 0.0))
	if act_k > 0.03:
		var tgt: Vector3 = inv * act_pos
		var sh: Vector3 = rig.tail("clavicle_r")
		var dv := tgt - sh
		if dv.length() > 0.24:
			tgt = sh + dv.normalized() * 0.24
		rig.arm("r", (rig.hang_arm_target("r", 0.0, 0.10) as Vector3).lerp(tgt, act_k), Vector3(-0.4, -0.6, 0.5))
	rig.apply()
	rig.tick(delta)


func _footfall(i: int, k: float) -> void:
	land_k = 1.0
	var p: Vector3 = feet[i]["pos"]
	if k > 0.35 and gait > 0.5 and p.y > water_y + 0.05 and not dust.is_empty():
		var fx := dust[dust_i % dust.size()]
		dust_i += 1
		fx.global_position = p
		fx.restart()


func _start_swing(i: int, to: Vector3, dur: float) -> void:
	var f := feet[i]
	to.y = ground.call(to.x, to.z) + ANKLE_H
	f["from"] = f["pos"]
	f["to"] = to
	f["swing"] = true
	f["t"] = 0.0
	f["dur"] = dur
