extends RefCounted
## 程序動畫骨架（吃 tools/camperlib.py 匯出的 Skeleton3D，骨名相同）。
## 做法：每根骨頭給「head 的位置」與「head→tail 的方向」，姿勢 = 把 rest 方向轉到目標方向的最小旋轉 × rest 姿勢
## （不含扭轉，所以不用管 Blender 的 bone roll；要扭就另外給 twist），再換算成相對父骨的 local 姿勢寫進 Skeleton3D。
## 腿、手臂用兩段式解析 IK（給末端目標與極向量）。座標都在模型空間：+X 前、+Y 上、+Z 右（左邊是 -Z）。

var sk: Skeleton3D
var idx := {}
var parent := {}
var rest_g := {}        # 骨名 → 全域 rest Transform3D
var rest_dir := {}      # 骨名 → rest 的 head→tail 方向（Blender 骨頭的 Y 軸）
var blen := {}          # 骨長
var g := {}             # 這一幀的全域姿勢
var torso_b := Basis()  # 這一幀胸腔的朝向（手臂用）
var face_mat: StandardMaterial3D
var blink_t := 0.0
var next_blink := 2.5
var rng := RandomNumberGenerator.new()

const ORDER := ["hips", "spine", "neck", "head", "clavicle_l", "upperarm_l", "forearm_l", "hand_l",
	"clavicle_r", "upperarm_r", "forearm_r", "hand_r", "pelvis_l", "thigh_l", "shin_l", "foot_l",
	"pelvis_r", "thigh_r", "shin_r", "foot_r"]
# 末端骨沒有子骨可量長度，用 camperlib 關節表的值
const LEAF_LEN := {"hips": 0.06, "head": 0.39, "hand_l": 0.055, "hand_r": 0.055, "foot_l": 0.128, "foot_r": 0.128}


func _init(skeleton: Skeleton3D, face: StandardMaterial3D = null) -> void:
	sk = skeleton
	face_mat = face
	rng.randomize()
	for i in sk.get_bone_count():
		var n := sk.get_bone_name(i)
		idx[n] = i
		var p := sk.get_bone_parent(i)
		parent[n] = sk.get_bone_name(p) if p >= 0 else ""
		rest_g[n] = sk.get_bone_global_rest(i)
	for n in idx:
		rest_dir[n] = (rest_g[n].basis * Vector3.UP).normalized()
		g[n] = rest_g[n]
	for n in idx:
		var child_len := 0.0
		for c in idx:
			if parent[c] == n:
				child_len = maxf(child_len, (rest_g[c].origin - rest_g[n].origin).length())
		blen[n] = child_len if child_len > 0.01 else LEAF_LEN.get(n, 0.1)


# ---------------------------------------------------------------- 基本

func set_bone(n: String, head: Vector3, dir: Vector3, twist := 0.0) -> void:
	var d := dir.normalized()
	var b: Basis = Basis(Quaternion(rest_dir[n] as Vector3, d)) * (rest_g[n] as Transform3D).basis
	if twist != 0.0:
		b = Basis(d, twist) * b
	g[n] = Transform3D(b, head)


func joint(n: String) -> Vector3:
	return g[n].origin


func tail(n: String) -> Vector3:
	return g[n].origin + (g[n].basis * Vector3.UP).normalized() * blen[n]


func apply() -> void:
	for n in ORDER:
		if not idx.has(n):
			continue
		var loc: Transform3D = g[n] if parent[n] == "" else (g[parent[n]] as Transform3D).affine_inverse() * g[n]
		var i: int = idx[n]
		sk.set_bone_pose_position(i, loc.origin)
		sk.set_bone_pose_rotation(i, loc.basis.get_rotation_quaternion())


func tick(delta: float) -> void:
	## 眨眼：貼圖右半格是閉眼
	if face_mat == null:
		return
	blink_t += delta
	if blink_t > next_blink + 0.13:
		blink_t = 0.0
		next_blink = rng.randf_range(2.0, 5.5)
		face_mat.uv1_offset.x = 0.0
	elif blink_t > next_blink:
		face_mat.uv1_offset.x = 0.5


# ---------------------------------------------------------------- 身體各部位

func torso(hips_pos: Vector3, yaw: float, pitch: float, roll: float, spine_yaw := 0.0, spine_pitch := 0.0,
		head_yaw := 0.0, head_pitch := 0.0, head_roll := 0.0) -> void:
	## pitch 正 = 前傾、roll 正 = 往右倒、yaw 正 = 往左轉（繞 +Y）。spine_* 疊在骨盆上、head_* 再疊在胸腔上。
	var hb := Basis(Vector3.UP, yaw) * Basis(Vector3.RIGHT, roll) * Basis(Vector3.BACK, -pitch)
	g["hips"] = Transform3D(hb * rest_g["hips"].basis, hips_pos)
	var sb := hb * Basis(Vector3.BACK, -spine_pitch)
	set_bone("spine", hips_pos, sb * rest_dir["spine"], spine_yaw)
	torso_b = hb * Basis(Vector3.UP, spine_yaw) * Basis(Vector3.BACK, -spine_pitch)
	var chest := tail("spine")
	set_bone("neck", chest, torso_b * rest_dir["neck"])
	var hd := torso_b * Basis(Vector3.RIGHT, head_roll) * Basis(Vector3.BACK, -head_pitch)
	set_bone("head", tail("neck"), hd * rest_dir["head"], head_yaw)
	for s in ["l", "r"]:
		set_bone("clavicle_" + s, chest, torso_b * rest_dir["clavicle_" + s])
		set_bone("pelvis_" + s, hips_pos, hb * rest_dir["pelvis_" + s])


func arm(side: String, hand_target: Vector3, pole: Vector3, hand_dir := Vector3.ZERO) -> void:
	var s := tail("clavicle_" + side)
	var r := _ik(s, hand_target, blen["upperarm_" + side], blen["forearm_" + side], pole)
	set_bone("upperarm_" + side, s, r[0])
	var e: Vector3 = r[1]
	var fd := (hand_target - e).normalized()
	set_bone("forearm_" + side, e, fd)
	set_bone("hand_" + side, e + fd * blen["forearm_" + side], hand_dir if hand_dir != Vector3.ZERO else fd)


func leg(side: String, ankle_target: Vector3, foot_dir: Vector3, pole := Vector3.RIGHT) -> void:
	var hj := tail("pelvis_" + side)
	var r := _ik(hj, ankle_target, blen["thigh_" + side], blen["shin_" + side], pole)
	set_bone("thigh_" + side, hj, r[0])
	var k: Vector3 = r[1]
	var sd := (ankle_target - k).normalized()
	set_bone("shin_" + side, k, sd)
	set_bone("foot_" + side, k + sd * blen["shin_" + side], foot_dir)


func hang_arm_target(side: String, swing: float, bend := 0.08) -> Vector3:
	## 手自然下垂、往前擺 swing 弧度（正 = 往前）的手腕目標點（模型空間）
	var s := tail("clavicle_" + side)
	var reach: float = (blen["upperarm_" + side] + blen["forearm_" + side]) * (1.0 - bend)
	return s + (torso_b * Basis(Vector3.BACK, -swing) * Vector3.DOWN) * reach


func rest_hip(side: String) -> Vector3:
	return rest_g["pelvis_" + side].origin + rest_dir["pelvis_" + side] * blen["pelvis_" + side]


func rest_ankle(side: String) -> Vector3:
	return rest_g["foot_" + side].origin


func _ik(root: Vector3, target: Vector3, l1: float, l2: float, pole: Vector3) -> Array:
	## 兩段式解析 IK：回傳 [第一段方向, 中間關節位置]；中間關節往 pole 那一側彎
	var d := target - root
	var L := clampf(d.length(), 0.02, l1 + l2 - 0.002)
	var dn := d / maxf(d.length(), 1e-6)
	var a := acos(clampf((l1 * l1 + L * L - l2 * l2) / (2.0 * l1 * L), -1.0, 1.0))
	var axis := dn.cross(pole)
	if axis.length() < 1e-4:
		axis = dn.cross(Vector3.UP if absf(dn.y) < 0.9 else Vector3.RIGHT)
	axis = axis.normalized()
	var dir1 := dn.rotated(axis, a)
	return [dir1, root + dir1 * l1]
