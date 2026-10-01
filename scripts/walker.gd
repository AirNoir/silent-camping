extends CharacterBody3D
## 散步模式的 Q 版露營者（forest.gd 按 P 建立）。
## WASD／方向鍵相對鏡頭方向走、Shift 跑。高度直接跟地形函式（不靠物理地板），
## move_and_slide 只負責跟道具（StaticBody3D）的水平碰撞。
## 走路是程序動畫（scripts/rig.gd）：腳真的踩住地面不滑——每隻腳在「落後髖部半步」時才抬起、
## 落到預測的下一步位置；膝蓋由兩段式 IK 決定；骨盆隨步伐起伏、側移、扭轉，肩膀反向，手臂跟對側腳同步擺。

const RigScript := preload("res://scripts/rig.gd")
const WALK := 1.15
const RUN := 2.6
const ACCEL := 9.0
const TURN := 9.0
const ANKLE_H := 0.09

var ground: Callable            # (x, z) -> 地面高度
var cam_yaw: Callable           # () -> 鏡頭 yaw，輸入方向以它為準
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
	cap.radius = 0.22
	cap.height = 1.1
	col.shape = cap
	col.position.y = 0.6
	add_child(col)
	motion_mode = CharacterBody3D.MOTION_MODE_FLOATING   # 高度自己管，不要物理重力與地板判定
	model.rotation.y = face
	for i in 2:
		feet.append({"pos": Vector3.ZERO, "from": Vector3.ZERO, "to": Vector3.ZERO, "swing": false, "t": 0.0, "dur": 0.25})
	reset_feet()


func reset_feet() -> void:
	## 出生／瞬移後把腳放回髖部正下方
	for i in 2:
		feet[i]["pos"] = _rest_foot_world(i)
		feet[i]["swing"] = false


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
	stride = 0.30 + 0.09 * speed
	var accel := (hv - prev_hv) / maxf(delta, 1e-4)
	prev_hv = hv
	# ---- 腳步：落後髖部半步就抬腳，落到預測位置；一次只有一隻腳在空中
	var swing_dur := clampf(0.55 * stride / maxf(speed, 0.4), 0.14, 0.32)
	for i in 2:
		var f := feet[i]
		var o := feet[1 - i]
		var hip_w: Vector3 = model.global_transform * Vector3(0.0, 0.0, rig.rest_hip("l" if i == 0 else "r").z)
		if not f["swing"]:
			if moving and not o["swing"]:
				var behind: float = (hip_w - f["pos"]).dot(heading)
				var lateral: float = absf((hip_w - f["pos"]).dot(side_w))
				if behind > stride * 0.5 or lateral > 0.22:
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
			p.y += (0.05 + 0.07 * k) * sin(PI * t)
			f["pos"] = p
			if t >= 1.0:
				f["swing"] = false
				f["pos"] = f["to"]
	# ---- 骨盆：支撐腳那一側墊高、往支撐腳側移、往擺動腿方向扭；跑步前傾
	var swing_i := -1
	var st := 0.0
	for i in 2:
		if feet[i]["swing"]:
			swing_i = i
			st = feet[i]["t"]
	var bob := 0.025 * gait * sin(PI * st) if swing_i >= 0 else 0.0
	var sway := (0.018 * gait * sin(PI * st) * (1.0 if swing_i == 0 else -1.0)) if swing_i >= 0 else 0.0   # 擺左腳 → 重心往右(+Z)
	var hip_yaw := (0.10 * gait * sin(PI * st) * (-1.0 if swing_i == 0 else 1.0)) if swing_i >= 0 else 0.0   # 擺左腳 → 左髖往前 = 繞 +Y 負轉
	var pitch := 0.05 * k * gait + clampf(accel.dot(heading) * 0.03, -0.12, 0.12)
	var inv := model.global_transform.affine_inverse()
	var hips := Vector3(0.0, 0.50 - 0.01 * gait + bob, sway)
	# 閒置：慢慢換重心、呼吸、東張西望
	var breathe := 0.015 * sin(idle_t * 1.6)
	look_timer -= delta
	if look_timer <= 0.0:
		look_timer = randf_range(2.5, 5.0)
		look_target = randf_range(-0.5, 0.5) * (1.0 - gait)
	look = lerpf(look, look_target * (1.0 - gait), 2.0 * delta)
	var idle_sway := 0.012 * (1.0 - gait) * sin(idle_t * 0.7)
	hips.z += idle_sway
	rig.torso(hips, hip_yaw, pitch + breathe * 0.5, lean * 0.3 + idle_sway * 1.5,
		-hip_yaw * 0.7, breathe, look - hip_yaw * 0.3, 0.04 * k * gait + 0.02 * sin(idle_t * 0.9), -lean * 0.4)
	# ---- 腿：腳踝目標 = 腳的世界位置轉回模型空間；腳掌抬起時腳尖往下
	for i in 2:
		var s := "l" if i == 0 else "r"
		var a_local: Vector3 = inv * (feet[i]["pos"] as Vector3)
		var toe_pitch := -0.5 * sin(PI * feet[i]["t"]) if feet[i]["swing"] else 0.0
		var fdir := Basis(Vector3.BACK, toe_pitch) * Vector3.RIGHT
		rig.leg(s, a_local, fdir, Vector3.RIGHT)
	# ---- 手臂：跟對側腳同步（腳在前 → 同側手在後），閒置時微微晃
	for i in 2:
		var s := "l" if i == 0 else "r"
		var hip_w: Vector3 = model.global_transform * Vector3(0.0, 0.0, rig.rest_hip(s).z)
		var fwd: float = clampf(((feet[i]["pos"] as Vector3) - hip_w).dot(heading) / maxf(stride, 0.1), -0.6, 0.6)
		var swing := -fwd * (0.9 + 0.6 * k) * gait + 0.03 * (1.0 - gait) * sin(idle_t * 1.3 + float(i) * 2.1)
		var bend := 0.06 + 0.10 * maxf(swing, 0.0) + 0.08 * k
		rig.arm(s, rig.hang_arm_target(s, swing, bend), Vector3(-1.0, -0.3, 0.0))
	rig.apply()
	rig.tick(delta)


func _start_swing(i: int, to: Vector3, dur: float) -> void:
	var f := feet[i]
	to.y = ground.call(to.x, to.z) + ANKLE_H
	f["from"] = f["pos"]
	f["to"] = to
	f["swing"] = true
	f["t"] = 0.0
	f["dur"] = dur
