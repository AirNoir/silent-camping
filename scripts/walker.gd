extends CharacterBody3D
## 散步模式的 Q 版露營者（forest.gd 按 P 建立）。
## WASD／方向鍵相對鏡頭方向走、Shift 跑。高度直接跟地形函式（不靠物理地板），
## move_and_slide 只負責跟道具（StaticBody3D）的水平碰撞。腿、手臂、頭是 GLB 裡原點在關節上的節點，走路循環用程式算。

const WALK := 2.2
const RUN := 4.2
const ACCEL := 10.0
const TURN := 10.0

var ground: Callable            # (x, z) -> 地面高度
var cam_yaw: Callable           # () -> 鏡頭 yaw，輸入方向以它為準
var bounds := 21.0              # 不走出地台
var water_y := -1.5
var auto_input := Vector2.ZERO  # debug／測試：固定輸入（x 右、y 後）
var auto_run := false

var model: Node3D
var head: Node3D
var legs: Array[Node3D] = []
var arms: Array[Node3D] = []
var phase := 0.0
var gait := 0.0                 # 0 站著 → 1 走路（平滑過渡，不會一停就僵住）
var speed := 0.0
var face := 0.0
var idle_t := 0.0


func setup(scene: Node3D) -> void:
	model = scene
	add_child(model)
	head = model.find_child("*_head", true, false)
	legs = [model.find_child("*_leg_l", true, false), model.find_child("*_leg_r", true, false)]
	arms = [model.find_child("*_arm_l", true, false), model.find_child("*_arm_r", true, false)]
	var col := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.22
	cap.height = 1.1
	col.shape = cap
	col.position.y = 0.6
	add_child(col)
	motion_mode = CharacterBody3D.MOTION_MODE_FLOATING   # 高度自己管，不要物理重力與地板判定


func _physics_process(delta: float) -> void:
	var inp := auto_input
	if inp == Vector2.ZERO:
		inp = Vector2(
			_key(KEY_D, KEY_RIGHT) - _key(KEY_A, KEY_LEFT),
			_key(KEY_S, KEY_DOWN) - _key(KEY_W, KEY_UP))
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
	speed = Vector2(velocity.x, velocity.z).length()
	_animate(delta)


func _key(a: Key, b: Key) -> float:
	return 1.0 if (Input.is_physical_key_pressed(a) or Input.is_physical_key_pressed(b)) else 0.0


func _animate(delta: float) -> void:
	var moving := speed > 0.15
	gait = move_toward(gait, 1.0 if moving else 0.0, 4.0 * delta)
	if moving:
		face = lerp_angle(face, atan2(-velocity.z, velocity.x), TURN * delta)   # 模型 +X 朝前
		phase += speed * delta * 3.4
	idle_t += delta
	model.rotation.y = face
	var k := clampf(speed / RUN, 0.0, 1.0)
	var swing := sin(phase) * gait
	var amp := 0.32 + 0.33 * k
	for i in 2:
		var s := 1.0 if i == 0 else -1.0
		if legs[i]:
			legs[i].rotation.z = s * amp * swing
		if arms[i]:
			arms[i].rotation.z = -s * amp * 0.7 * swing + 0.04 * (1.0 - gait) * sin(idle_t * 1.3 + float(i))
	model.position.y = 0.04 * absf(swing) * k
	model.rotation.z = -0.10 * k * gait   # 跑起來往前傾
	if head:
		head.rotation = Vector3(0.03 * sin(idle_t * 0.7), 0.0, 0.04 * sin(idle_t * 0.9) + 0.03 * absf(swing) * k)
