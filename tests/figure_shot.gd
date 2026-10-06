extends SceneTree
## 角色模型擺進營地截圖（實際遊戲比例 1:1）：預設把 character_base 放在帳篷前，旁邊放第三代露營者對照。
## Godot --path . --script res://tests/figure_shot.gd --write-movie out.png --fixed-fps 30 --quit-after 40 -- [選項]
##   --model=<gen 底下的 glb 名稱>   預設 character_base
##   --walkcam                       用散步模式的第三人稱鏡頭（真正的遊戲鏡頭）：角色站在 walker 的位置，舊模型藏起來
##   --walkdist=<m>                  散步鏡頭距離（預設 5.5；拉遠看遠景）
##   --orbit=<dist>,<pitch_deg>      用環繞（模型）鏡頭、以角色為中心拉遠看（遠景）
##   --at=x,z,cx,cz                  角色位置與鏡頭方向參考點（預設帳篷前）
##   --cam-rel=x,y,z,tx,ty,tz,fov    自訂鏡頭（forest.gd 處理）

var FIG := Vector2(-6.7, -4.3)
var CAM := Vector2(-4.6, -1.7)

var main: Node3D
var placed := false
var model := "character_base"
var walkcam := false
var walkdist := 0.0
var orbit := Vector2.ZERO


func _initialize() -> void:
	for arg: String in OS.get_cmdline_user_args():
		if arg.begins_with("--model="):
			model = arg.trim_prefix("--model=")
		elif arg == "--walkcam":
			walkcam = true
		elif arg.begins_with("--walkdist="):
			walkdist = float(arg.trim_prefix("--walkdist="))
		elif arg.begins_with("--orbit="):
			var o := arg.trim_prefix("--orbit=").split_floats(",")
			orbit = Vector2(o[0], o[1])
		elif arg.begins_with("--at="):
			var v := arg.trim_prefix("--at=").split_floats(",")
			FIG = Vector2(v[0], v[1])
			CAM = Vector2(v[2], v[3])
	main = (load("res://forest.tscn") as PackedScene).instantiate()
	root.add_child(main)


func _process(_d: float) -> bool:
	if placed:
		return false
	placed = true   # 等 forest._ready() 設好地形噪聲再擺，h() 才對
	var to_cam := CAM - FIG
	var rot := atan2(-to_cam.y, to_cam.x)   # 模型正面是 +X
	main.place_scene("gen/" + model, FIG.x, FIG.y, rot)
	var side := Vector2(-to_cam.y, to_cam.x).normalized() * 0.75
	main.place_scene("gen/camper_walk", FIG.x + side.x, FIG.y + side.y, rot)
	if walkcam:
		main._enter_walk()
		main.walker.position = Vector3(FIG.x, main.h(FIG.x, FIG.y), FIG.y)
		main.walker.model.visible = false
		main.yaw = atan2(to_cam.x, to_cam.y)   # 鏡頭在角色往 CAM 的方向後方
		if walkdist > 0.0:
			main.dist = walkdist
			main.walk_cam_d = walkdist
	if orbit != Vector2.ZERO:
		main.pivot.position = Vector3(FIG.x, main.h(FIG.x, FIG.y) + 0.5, FIG.y)
		main.dist = orbit.x
		main.pitch = deg_to_rad(orbit.y)
		main.yaw = atan2(to_cam.x, to_cam.y)
	return false
