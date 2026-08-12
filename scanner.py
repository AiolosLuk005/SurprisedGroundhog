import os
import hashlib
import random
import datetime
from sqlalchemy.orm import Session
from .db import FileORM, SessionLocal

# 用于模拟 AI 预测的词库和规则
AI_KEYWORDS_POOL = ["战场", "废墟", "黄昏", "硝烟", "坦克残骸", "法师", "魔法阵", "紫色长袍", "水晶杖", "夜晚森林", "月光", "萤火虫", "迷雾", "爆炸", "火焰", "粒子", "冲击波", "HUD", "血条", "弹药计数", "小地图", "跑步循环", "角色动画", "骨骼", "石墙", "漫反射贴图", "无缝纹理", "中世纪", "龙", "高模", "鳞片", "雨", "环境音", "巡逻", "追击", "水面", "菲涅尔", "传送点", "NPC分布", "骑士", "盔甲", "宝箱", "开箱动画", "CG", "沙漠", "沙丘"]

SCENE_POOL = ["战场", "奇幻城堡", "暗夜森林", "中世纪城堡", "龙穴", "海洋", "开放世界", "地下城", "沙漠", "通用"]
CATEGORY_POOL = ["场景原画", "角色设计", "环境贴图", "特效序列", "UI设计", "角色动画", "PBR贴图", "3D模型", "音效素材", "游戏脚本", "着色器", "关卡数据", "3D道具", "过场动画", "地形数据", "粒子特效", "资源字体", "后处理", "导航数据"]
ENTITY_POOL = ["坦克", "废墟", "法师", "魔法杖", "树木", "月亮", "火焰", "碎片", "血条", "小地图", "人物", "骨骼", "石墙", "龙", "翅膀", "雨", "雷声", "AI行为树", "水面", "波浪", "地图", "传送门", "骑士", "盔甲", "宝箱", "金币", "军队", "城堡", "沙丘", "岩石", "字体", "魔法阵", "光球", "LUT", "色调", "导航网格"]
TIME_POOL = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4", "2025-Q1"]

def get_file_md5(filepath: str) -> str:
    """计算文件 MD5"""
    hasher = hashlib.md5()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error calculating MD5 for {filepath}: {e}")
        # 如果文件无法打开（比如被占用），使用文件属性生成哈希
        stat = os.stat(filepath)
        dummy_str = f"{filepath}_{stat.st_mtime}_{stat.st_size}"
        return hashlib.md5(dummy_str.encode('utf-8')).hexdigest()

def simulate_ai_tagging(filename: str, file_type: str):
    """根据文件名和类型，模拟 AI 预测生成标签、关键词和置信度"""
    filename_lower = filename.lower()
    
    # 1. 筛选匹配关键词
    keywords = []
    for kw in AI_KEYWORDS_POOL:
        if kw in filename_lower:
            keywords.append(kw)
    # 如果没匹配到，随机分配 2-3 个
    if not keywords:
        keywords = random.sample(AI_KEYWORDS_POOL, k=random.randint(2, 4))
        
    # 2. 预测场景
    scene = []
    if "scene" in filename_lower or "battlefield" in filename_lower:
        scene = ["战场"]
    elif "forest" in filename_lower:
        scene = ["暗夜森林"]
    elif "castle" in filename_lower or "mage" in filename_lower:
        scene = ["奇幻城堡"]
    elif "dungeon" in filename_lower:
        scene = ["地下城"]
    else:
        scene = [random.choice(SCENE_POOL)]
        
    # 3. 预测分类
    category = []
    if file_type in ["psd", "png", "tga"] and "concept" in filename_lower:
        category = ["场景原画" if "scene" in filename_lower else "角色设计"]
    elif file_type in ["fbx", "obj", "blend", "glb"]:
        category = ["3D模型" if "highpoly" in filename_lower else "3D道具"]
    elif "anim" in filename_lower:
        category = ["角色动画"]
    elif file_type in ["wav", "mp3"]:
        category = ["音效素材"]
    elif file_type == "py":
        category = ["游戏脚本"]
    else:
        category = [random.choice(CATEGORY_POOL)]
        
    # 4. 预测关联实体
    entities = []
    for ent in ENTITY_POOL:
        if ent in filename_lower:
            entities.append(ent)
    if not entities:
        entities = random.sample(ENTITY_POOL, k=random.randint(1, 2))
        
    # 5. 周期
    time_period = [random.choice(TIME_POOL)]
    
    # 6. 置信度：随机在 25% - 98% 之间，生成红/黄/绿不同级别的置信度以供审核
    ai_confidence = round(random.uniform(25.0, 98.0), 1)
    
    return {
        "ai_keywords": keywords,
        "scene": scene,
        "category": category,
        "entity": entities,
        "time_period": time_period,
        "ai_confidence": ai_confidence
    }

def scan_directory(scan_dir: str):
    """扫描指定文件夹并将新增文件录入数据库"""
    if not os.path.exists(scan_dir):
        print(f"Warning: Scan directory '{scan_dir}' does not exist. Creating it...")
        os.makedirs(scan_dir, exist_ok=True)
        # 生成一个测试文件包以供扫描
        create_test_assets(scan_dir)
        
    db: Session = SessionLocal()
    try:
        scanned_count = 0
        inserted_count = 0
        updated_count = 0
        
        for root, dirs, files in os.walk(scan_dir):
            # 排除隐藏目录、临时目录及旧虚拟环境
            dirs[:] = [
                d for d in dirs
                if not d.startswith('.')
                and d not in ['__pycache__', 'node_modules', 'venv', '.venv', 'env']
            ]

            for file in files:
                scanned_count += 1
                filepath = os.path.join(root, file).replace('\\', '/')
                # 文件名超长保护（VARCHAR(255) 限制）
                filename = file[:255] if len(file) > 255 else file
                
                try:
                    file_size = os.path.getsize(filepath)
                    file_type = os.path.splitext(file)[1].replace('.', '').lower()

                    # 计算 MD5
                    md5_val = get_file_md5(filepath)

                    # 查询数据库中是否已存在
                    existing_file = db.query(FileORM).filter(FileORM.filepath == filepath).first()

                    if not existing_file:
                        # AI 模拟标签生成
                        ai_meta = simulate_ai_tagging(filename, file_type)

                        # 写入新记录
                        new_asset = FileORM(
                            filename=filename,
                            filepath=filepath,
                            file_size=file_size,
                            file_type=file_type or "unknown",
                            md5=md5_val,
                            ai_keywords=ai_meta["ai_keywords"],
                            scene=ai_meta["scene"],
                            category=ai_meta["category"],
                            entity=ai_meta["entity"],
                            time_period=ai_meta["time_period"],
                            ai_confidence=ai_meta["ai_confidence"],
                            review_status=0  # 待审批
                        )
                        db.add(new_asset)
                        db.flush()  # 立即写入（验证约束），不提交事务
                        inserted_count += 1
                        print(f"[NEW] Scanned & Inserted: {filename} (Confidence: {ai_meta['ai_confidence']}%)")
                    else:
                        # 如果文件 MD5 改变，更新元数据，并重置审批状态
                        if existing_file.md5 != md5_val:
                            ai_meta = simulate_ai_tagging(filename, file_type)
                            existing_file.file_size = file_size
                            existing_file.md5 = md5_val
                            existing_file.ai_keywords = ai_meta["ai_keywords"]
                            existing_file.scene = ai_meta["scene"]
                            existing_file.category = ai_meta["category"]
                            existing_file.entity = ai_meta["entity"]
                            existing_file.time_period = ai_meta["time_period"]
                            existing_file.ai_confidence = ai_meta["ai_confidence"]
                            existing_file.review_status = 0
                            existing_file.updated_at = datetime.datetime.utcnow()
                            updated_count += 1
                            print(f"[UPDATE] File changed, updated db: {filename}")

                except Exception as file_err:
                    # 单文件失败不影响整批，回滚当前挂起更改后继续
                    db.rollback()
                    print(f"[SKIP] Error processing '{filename}': {file_err}")

        db.commit()
        print(f"\n--- Scan Complete ---")
        print(f"Total Scanned: {scanned_count}")
        print(f"Inserted New:  {inserted_count}")
        print(f"Updated:       {updated_count}")

    except Exception as e:
        db.rollback()
        print(f"Error during directory scanning: {e}")
    finally:
        db.close()

def create_test_assets(scan_dir: str):
    """如果目录为空，自动生成几个空测试文件以供扫描调试"""
    test_files = [
        ("scene_desert_fortress.psd", 45000000),
        ("char_knight_animation_run.fbx", 12000000),
        ("audio_dungeon_bgm.wav", 8000000),
        ("shader_ocean_foam.hlsl", 15000),
        ("prop_magic_portal_lowpoly.obj", 3200000),
    ]
    for filename, size in test_files:
        filepath = os.path.join(scan_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                # 写入指定大小的空数据
                f.seek(size - 1)
                f.write(b'\0')
            print(f"Created test asset: {filename} ({size} bytes)")
        except Exception as e:
            print(f"Failed to create test asset {filename}: {e}")
