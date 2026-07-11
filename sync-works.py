#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
营口机车影像 · 一键同步作品

精选三栏（按项目上传）：
  assets/portfolio/photo/城市追光/   ← 动态跟拍视频
  assets/portfolio/photo/夜色锋芒/   ← 夜晚拍摄素材
  assets/portfolio/photo/港湾日光/   ← 白天拍摄素材

AIGC 按项目：
  assets/portfolio/aigc/video/项目名/
  assets/portfolio/aigc/design/项目名/

双击「更新作品.command」或：python3 sync-works.py

视频封面：
  - 若项目内没有 cover.jpg / {视频名}-cover.jpg，同步时会自动从视频截帧生成
  - 也可手动放 cover.jpg 覆盖自动封面

自动命名：
  - 识别 DSC / ChatGPT / grok-video / 纯数字 等不规范文件名
  - 重命名为「项目名-01.jpg」「项目名.mp4」等形式
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORKS_JS = ROOT / "works.js"
TITLES_JSON = ROOT / "titles.json"
RENAME_LOG = ROOT / "rename-log.json"

IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXT = {".mp4", ".mov", ".webm"}
SKIP_DIR_NAMES = {"web", "_unused-covers", "_originals", "moto", "film", ".git"}
SKIP_NAMES = {".ds_store", "thumbs.db"}
SKIP_NAME_PARTS = (".original.", ".web.tmp.", ".tmp.")
COVER_NAMES = {"cover", "poster", "thumb", "thumbnail"}

# 视为「未准确命名」的文件名模式（匹配 stem）
BAD_NAME_PATTERNS = [
    re.compile(r"^DSC\d+$", re.I),
    re.compile(r"^IMG[_\-]?\d+$", re.I),
    re.compile(r"^Image\s*\d+$", re.I),
    re.compile(r"^ChatGPT", re.I),
    re.compile(r"^grok-video-", re.I),
    re.compile(r"^Screenshot", re.I),
    re.compile(r"^Screen Shot", re.I),
    re.compile(r"^微信图片", re.I),
    re.compile(r"^mmexport\d+$", re.I),
    re.compile(r"^\d{8,}"),  # 长数字串
    re.compile(r"^\d+$"),  # 纯数字 1.mp4
    re.compile(r"^moto-film-\d+$", re.I),
    re.compile(r"^aigc-", re.I),
    re.compile(r"^image[-_]", re.I),
    re.compile(r"^photo[-_]?\d*$", re.I),
    re.compile(r"^视频", re.I),
    re.compile(r"^新建", re.I),
]

# 精选作品三栏：固定文件夹名 + 展示文案
FEATURED_SLOTS = [
    {
        "folder": "城市追光",
        "number": "01",
        "layout": "wide",
        "label": "城市追光",
        "title": "沿海公路 / Red Line",
        "subtitle": "动态跟拍电影感短片 · 点击查看项目",
        "cat": "film",
        "kind": "video",  # 大卡优先用视频预览
    },
    {
        "folder": "夜色锋芒",
        "number": "02",
        "layout": "normal",
        "label": "约拍作品集",
        "title": "夜色锋芒 / Night Edge",
        "subtitle": "夜间拍摄素材 · 点击查看项目",
        "cat": "moto-night",
        "kind": "image",
    },
    {
        "folder": "港湾日光",
        "number": "03",
        "layout": "normal",
        "label": "日间约拍",
        "title": "港湾日光 / Harbor Light",
        "subtitle": "白天拍摄素材 · 点击查看项目",
        "cat": "moto-day",
        "kind": "image",
    },
]


def load_titles() -> dict:
    if not TITLES_JSON.exists():
        return {}
    try:
        data = json.loads(TITLES_JSON.read_text(encoding="utf-8"))
        return {str(k): str(v) for k, v in data.items() if not str(k).startswith("_")}
    except Exception as e:
        print(f"⚠ titles.json 读取失败: {e}")
        return {}


def stem_title(name: str, titles: dict) -> str:
    if name in titles:
        return titles[name]
    stem = Path(name).stem
    stem = re.sub(r"[-_](cover|poster|thumb)$", "", stem, flags=re.I)
    if stem in titles:
        return titles[stem]
    if re.match(r"^DSC\d+", stem, re.I):
        return stem.upper()
    return stem.replace("_", " ").replace("-", " ").strip() or stem


def project_title(folder_name: str, titles: dict) -> str:
    return titles.get(folder_name, folder_name.replace("_", " ").replace("-", " ").strip())


def slug_id(*parts: str) -> str:
    raw = "-".join(parts)
    safe = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff\-]+", "-", raw).strip("-").lower()
    return (safe or "item")[:100]


def is_skipped_file(p: Path) -> bool:
    if not p.is_file() or p.name.startswith("."):
        return True
    if p.name.lower() in SKIP_NAMES:
        return True
    low = p.name.lower()
    return any(part in low for part in SKIP_NAME_PARTS)


def is_cover_file(p: Path) -> bool:
    stem = p.stem.lower()
    if stem in COVER_NAMES:
        return True
    return stem.endswith("-cover") or stem.endswith("_cover") or stem.endswith("-poster")


def is_bad_name(filename: str) -> bool:
    """判断是否需要自动重命名。"""
    stem = Path(filename).stem
    # 已是「中文项目名-01」则跳过
    if re.match(r"^[\u4e00-\u9fff].*-\d{2,}$", stem):
        return False
    # 已是以中文开头的语义名（视频常用，如 彩妆广告 / 鲅鱼公主）
    if re.match(r"^[\u4e00-\u9fff]", stem):
        if any(p.search(stem) for p in BAD_NAME_PATTERNS):
            return True
        # 纯中文或中文+少量字符
        if re.match(r"^[\u4e00-\u9fff][\u4e00-\u9fffA-Za-z0-9·\-\s]{0,40}$", stem):
            return False
    for p in BAD_NAME_PATTERNS:
        if p.search(stem):
            return True
    # 含空格+长英文机器名
    if " " in stem and len(stem) > 20:
        return True
    if re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", stem, re.I):
        return True
    return False


def safe_project_slug(name: str) -> str:
    """项目文件夹名 → 文件名前缀（保留中文）。"""
    s = name.strip()
    s = re.sub(r'[\\/:*?"<>|]+', "", s)
    s = re.sub(r"\s+", "", s)
    return s or "作品"


def unique_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    i = 2
    while True:
        cand = dest.with_name(f"{dest.stem}-{i}{dest.suffix}")
        if not cand.exists():
            return cand
        i += 1


def auto_rename_project_media(project_dir: Path) -> list[dict]:
    """
    将项目文件夹内命名不规范的媒体重命名为：
      图片：项目名-01.jpg / 项目名-02.jpg
      视频：项目名.mp4 或 项目名-01.mp4（多条时）
    返回重命名记录 [{old, new, title}, ...]
    """
    if not project_dir.is_dir():
        return []
    prefix = safe_project_slug(project_dir.name)
    records: list[dict] = []

    # 只处理项目根目录媒体，不处理 web/、cover 专用文件
    images = [
        p
        for p in list_files(project_dir, IMG_EXT)
        if not is_cover_file(p) and p.stem.lower() not in COVER_NAMES
    ]
    videos = list_files(project_dir, VID_EXT)

    # —— 图片 ——
    bad_imgs = [p for p in images if is_bad_name(p.name)]
    good_imgs = [p for p in images if not is_bad_name(p.name)]
    # 已是规范序号的也纳入序号占用
    used_nums: set[int] = set()
    for p in good_imgs:
        m = re.search(r"-(\d{2,})$", p.stem)
        if m:
            used_nums.add(int(m.group(1)))

    # 按拍摄时间/文件名排序后重命名 bad
    bad_imgs_sorted = sorted(bad_imgs, key=lambda p: (p.stat().st_mtime, p.name))
    next_num = 1
    for src in bad_imgs_sorted:
        while next_num in used_nums:
            next_num += 1
        # 统一输出 jpg（png 大图也转 jpg 便于网站）
        ext = ".jpg" if src.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else src.suffix.lower()
        new_name = f"{prefix}-{next_num:02d}{ext}"
        dest = unique_path(project_dir / new_name)
        old_name = src.name
        try:
            if ext == ".jpg" and src.suffix.lower() != ".jpg":
                # 转 jpg
                run_sips_optimize(src, dest, max_edge=4000, quality=90)
                if dest.exists():
                    src.unlink(missing_ok=True)
                else:
                    src.rename(dest)
            else:
                src.rename(dest)
            used_nums.add(next_num)
            title = f"{project_dir.name} · {next_num:02d}"
            records.append({"old": old_name, "new": dest.name, "title": title, "dir": str(project_dir.relative_to(ROOT))})
            print(f"  命名 {old_name} → {dest.name}")
            # 清理旧 web 缓存
            old_web = project_dir / "web" / f"{Path(old_name).stem}.jpg"
            if old_web.exists():
                old_web.unlink(missing_ok=True)
            next_num += 1
        except Exception as e:
            print(f"  ⚠ 重命名失败 {old_name}: {e}")

    # —— 视频 ——
    bad_vids = [p for p in videos if is_bad_name(p.name)]
    if bad_vids:
        bad_vids_sorted = sorted(bad_vids, key=lambda p: (p.stat().st_mtime, p.name))
        multi = len(videos) > 1
        vnum = 1
        for src in bad_vids_sorted:
            if multi:
                while True:
                    new_name = f"{prefix}-{vnum:02d}{src.suffix.lower()}"
                    dest = project_dir / new_name
                    if not dest.exists() or dest == src:
                        break
                    vnum += 1
            else:
                new_name = f"{prefix}{src.suffix.lower()}"
                dest = project_dir / new_name
                if dest.exists() and dest != src:
                    dest = unique_path(dest)
            old_name = src.name
            try:
                if dest != src:
                    src.rename(dest)
                # 同步重命名关联封面
                for suf in ("-cover.jpg", "_cover.jpg", ".jpg", ".png"):
                    old_c = project_dir / f"{Path(old_name).stem}{suf}"
                    if old_c.exists() and suf.startswith("-"):
                        new_c = project_dir / f"{dest.stem}-cover.jpg"
                        if not new_c.exists():
                            old_c.rename(new_c) if suf != ".png" else None
                            if suf == ".png" or (old_c.exists() and old_c.suffix.lower() == ".png"):
                                run_sips_optimize(old_c, new_c, max_edge=1600, quality=85)
                                old_c.unlink(missing_ok=True)
                title = project_dir.name if not multi else f"{project_dir.name} · {vnum:02d}"
                records.append({"old": old_name, "new": dest.name, "title": title, "dir": str(project_dir.relative_to(ROOT))})
                print(f"  命名视频 {old_name} → {dest.name}")
                vnum += 1
            except Exception as e:
                print(f"  ⚠ 视频重命名失败 {old_name}: {e}")

    return records


def iter_all_project_dirs() -> list[Path]:
    """遍历所有应自动命名的项目目录。"""
    dirs: list[Path] = []
    photo = ROOT / "assets/portfolio/photo"
    for slot in ("城市追光", "夜色锋芒", "港湾日光"):
        slot_dir = photo / slot
        if not slot_dir.exists():
            continue
        for sub in project_dirs(slot_dir):
            dirs.append(sub)
    for kind in ("video", "design"):
        base = ROOT / "assets/portfolio/aigc" / kind
        if not base.exists():
            continue
        for sub in project_dirs(base):
            dirs.append(sub)
    return dirs


def run_auto_rename_all() -> list[dict]:
    print("\n=== 自动规范命名 ===")
    all_recs: list[dict] = []
    for d in iter_all_project_dirs():
        recs = auto_rename_project_media(d)
        if recs:
            print(f"  [{d.relative_to(ROOT)}] 重命名 {len(recs)} 个文件")
            all_recs.extend(recs)
    if not all_recs:
        print("  无需重命名（或已是规范名）")
    else:
        # 合并写入 titles.json
        titles = load_titles()
        for r in all_recs:
            stem = Path(r["new"]).stem
            titles[stem] = r["title"]
            titles[r["new"]] = r["title"]
        # 保留说明键
        existing = {}
        if TITLES_JSON.exists():
            try:
                existing = json.loads(TITLES_JSON.read_text(encoding="utf-8"))
            except Exception:
                pass
        note = existing.get("_说明", "键=文件名或项目名，值=展示标题。同步时会自动写入规范名。")
        out = {"_说明": note, **{k: v for k, v in titles.items() if not str(k).startswith("_")}}
        TITLES_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # 日志
        log = []
        if RENAME_LOG.exists():
            try:
                log = json.loads(RENAME_LOG.read_text(encoding="utf-8"))
            except Exception:
                log = []
        log.extend(all_recs)
        RENAME_LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"  共重命名 {len(all_recs)} 个文件（详见 rename-log.json）")
    return all_recs


def run_sips_optimize(src: Path, dest: Path, max_edge: int = 1600, quality: int = 82) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [
                "sips", "-Z", str(max_edge),
                "-s", "format", "jpeg",
                "-s", "formatOptions", str(quality),
                str(src), "--out", str(dest),
            ],
            check=True,
            capture_output=True,
        )
        return dest.exists()
    except Exception as e:
        print(f"  ⚠ 压缩失败 {src.name}: {e}")
        return False


def ensure_web_image(src: Path, web_dir: Path) -> Path | None:
    if src.suffix.lower() not in IMG_EXT:
        return None
    dest = web_dir / f"{src.stem}.jpg"
    need = (not dest.exists()) or (src.stat().st_mtime > dest.stat().st_mtime)
    if need or src.stat().st_size > 700_000:
        print(f"  压缩 {src.relative_to(ROOT)} → {dest.relative_to(ROOT)}")
        if not run_sips_optimize(src, dest):
            return src
    return dest if dest.exists() else src


def _find_existing_cover(video: Path, project_dir: Path) -> Path | None:
    """查找已有封面（不生成）。"""
    stem = video.stem
    candidates = [
        project_dir / "cover.jpg",
        project_dir / "cover.png",
        project_dir / f"{stem}-cover.jpg",
        project_dir / f"{stem}_cover.jpg",
        project_dir / f"{stem}.jpg",
        project_dir / f"{stem}.png",
        project_dir / "poster.jpg",
        project_dir / "web" / "cover.jpg",
        project_dir / "web" / f"{stem}-cover.jpg",
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 1000:
            return c
    return None


def extract_video_cover(video: Path, out: Path, prefer_times: list[float] | None = None) -> bool:
    """
    从视频截取封面帧。
    优先 remotion ffmpeg；失败则用 macOS Swift/AVFoundation。
    会尝试多个时间点，避开过黑/过亮帧。
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    times = prefer_times or [1.0, 0.5, 2.0, 3.0, 0.2, 5.0]

    # 1) ffmpeg（remotion 自带）
    remotion_ffmpeg = Path(
        "/Users/zhangjun/Documents/Codex New project/remotion-cut/node_modules/"
        "@remotion/compositor-darwin-arm64"
    )
    ffmpeg = remotion_ffmpeg / "ffmpeg"
    if ffmpeg.exists():
        env = dict(**{k: v for k, v in __import__("os").environ.items()})
        env["DYLD_LIBRARY_PATH"] = str(remotion_ffmpeg)
        for t in times:
            tmp = out.with_suffix(".tmp.jpg")
            try:
                r = subprocess.run(
                    [
                        str(ffmpeg), "-y",
                        "-ss", str(t),
                        "-i", str(video),
                        "-frames:v", "1",
                        "-q:v", "2",
                        str(tmp),
                    ],
                    capture_output=True,
                    env=env,
                    timeout=60,
                )
                if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 2000:
                    # 简单亮度检测：用 sips 无法直接读，文件够大就接受
                    tmp.replace(out)
                    return True
            except Exception:
                pass
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    # 2) Swift AVFoundation：多时间点选反差较好的帧
    times_lit = ", ".join(str(t) for t in times)
    out_escaped = str(out).replace("\\", "\\\\").replace('"', '\\"')
    vid_escaped = str(video).replace("\\", "\\\\").replace('"', '\\"')
    swift = f'''
import Foundation
import AVFoundation
import AppKit

let src = URL(fileURLWithPath: "{vid_escaped}")
let out = URL(fileURLWithPath: "{out_escaped}")
let asset = AVURLAsset(url: src)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true
gen.maximumSize = CGSize(width: 1600, height: 1600)
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero

struct Cand {{ var sec: Double; var score: Double; var data: Data }}
var best: Cand? = nil
let times: [Double] = [{times_lit}]

for sec in times {{
  let t = CMTime(seconds: sec, preferredTimescale: 600)
  do {{
    let cg = try gen.copyCGImage(at: t, actualTime: nil)
    let rep = NSBitmapImageRep(cgImage: cg)
    var sum = 0.0, sum2 = 0.0, n = 0.0
    let stepX = max(1, rep.pixelsWide / 40)
    let stepY = max(1, rep.pixelsHigh / 40)
    for y in stride(from: 0, to: rep.pixelsHigh, by: stepY) {{
      for x in stride(from: 0, to: rep.pixelsWide, by: stepX) {{
        var r: CGFloat=0, g: CGFloat=0, b: CGFloat=0, a: CGFloat=0
        rep.colorAt(x: x, y: y)?.getRed(&r, green: &g, blue: &b, alpha: &a)
        let v = Double(r+g+b)/3
        sum += v; sum2 += v*v; n += 1
      }}
    }}
    guard n > 0 else {{ continue }}
    let avg = sum / n
    let variance = max(0, sum2/n - avg*avg)
    // 避开全黑/全白，偏好有细节的帧
    if avg < 0.08 || avg > 0.92 {{ continue }}
    let score = variance * 2 + (1.0 - abs(avg - 0.45))
    if let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.88]) {{
      if best == nil || score > best!.score {{
        best = Cand(sec: sec, score: score, data: data)
      }}
    }}
  }} catch {{ }}
}}

if let b = best {{
  try b.data.write(to: out)
  print("swift-cover t=\\(b.sec) bytes=\\(b.data.count)")
  exit(0)
}}
// 兜底：取 1s 帧
do {{
  let t = CMTime(seconds: 1.0, preferredTimescale: 600)
  let cg = try gen.copyCGImage(at: t, actualTime: nil)
  let rep = NSBitmapImageRep(cgImage: cg)
  if let data = rep.representation(using: .jpeg, properties: [.compressionFactor: 0.88]) {{
    try data.write(to: out)
    print("swift-cover-fallback bytes=\\(data.count)")
    exit(0)
  }}
}} catch {{
  fputs("err \\(error)\\n", stderr)
  exit(1)
}}
exit(1)
'''
    try:
        r = subprocess.run(
            ["swift", "-e", swift],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if out.exists() and out.stat().st_size > 2000:
            if r.stdout.strip():
                print(f"    {r.stdout.strip()}")
            return True
        if r.stderr:
            print(f"  ⚠ 截帧失败: {r.stderr.strip()[:200]}")
    except Exception as e:
        print(f"  ⚠ 截帧异常: {e}")
    return False


def ensure_video_cover(video: Path, project_dir: Path, also_project_cover: bool = True) -> Path | None:
    """
    确保视频有封面：
    - 单条视频：{stem}-cover.jpg
    - 项目级：cover.jpg（若尚无）
    返回用于条目的封面路径。
    """
    existing = _find_existing_cover(video, project_dir)
    if existing:
        # 若尚无项目 cover.jpg，复制一份方便卡片展示
        project_cover = project_dir / "cover.jpg"
        if also_project_cover and not project_cover.exists():
            try:
                if existing.suffix.lower() == ".jpg":
                    import shutil
                    shutil.copy2(existing, project_cover)
                else:
                    run_sips_optimize(existing, project_cover, max_edge=1600, quality=85)
            except Exception:
                pass
        return existing

    stem_cover = project_dir / f"{video.stem}-cover.jpg"
    project_cover = project_dir / "cover.jpg"

    print(f"  自动截取封面: {video.relative_to(ROOT)}")
    ok = extract_video_cover(video, stem_cover)
    if not ok:
        return None

    # 压到合适体积
    if stem_cover.stat().st_size > 800_000:
        run_sips_optimize(stem_cover, stem_cover, max_edge=1600, quality=85)

    if also_project_cover and not project_cover.exists():
        import shutil
        shutil.copy2(stem_cover, project_cover)

    print(f"  ✓ 封面已生成 → {stem_cover.relative_to(ROOT)}")
    return stem_cover


def list_files(folder: Path, exts: set[str]) -> list[Path]:
    if not folder.exists():
        return []
    out = []
    for p in sorted(folder.iterdir()):
        if is_skipped_file(p):
            continue
        if p.suffix.lower() in {e.lower() for e in exts}:
            out.append(p)
    return out


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def js_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render_item(it: dict, indent: int = 2) -> str:
    sp = " " * indent
    lines = [f"{sp}{{"]
    for key in ("id", "cat", "type", "title", "meta", "cover", "src", "project"):
        if key in it and it[key] is not None:
            lines.append(f"{sp}  {key}: {js_string(it[key])},")
    lines.append(f"{sp}}},")
    return "\n".join(lines)


# ── 摄影精选三项目 ───────────────────────────────────────


def collect_media_project(
    project_dir: Path,
    cat: str,
    meta_prefix: str,
    titles: dict,
    allow_video: bool,
    allow_image: bool,
) -> dict | None:
    """通用项目扫描：图片进 web/，视频保留，cover.jpg 作封面。"""
    if not project_dir.exists():
        project_dir.mkdir(parents=True, exist_ok=True)
        print(f"  已创建空项目文件夹: {project_dir.relative_to(ROOT)}")
        return None

    web_dir = project_dir / "web"
    items: list[dict] = []
    images = list_files(project_dir, IMG_EXT)
    image_map = {p.stem.lower(): p for p in images}

    if allow_image:
        for src in images:
            if is_cover_file(src) and src.stem.lower() in COVER_NAMES:
                continue
            # 视频封面图不单独登记为作品
            if is_cover_file(src):
                continue
            web = ensure_web_image(src, web_dir)
            if not web:
                continue
            items.append(
                {
                    "id": slug_id(cat, project_dir.name, src.stem),
                    "cat": cat,
                    "type": "image",
                    "title": stem_title(src.name, titles),
                    "meta": f"{meta_prefix} · {project_title(project_dir.name, titles)}",
                    "src": rel(web),
                    "project": project_dir.name,
                }
            )
        if web_dir.exists():
            have = {Path(i["src"]).stem for i in items}
            for web in list_files(web_dir, IMG_EXT):
                if web.stem.lower() in COVER_NAMES or web.stem in have:
                    continue
                items.append(
                    {
                        "id": slug_id(cat, project_dir.name, web.stem),
                        "cat": cat,
                        "type": "image",
                        "title": stem_title(web.name, titles),
                        "meta": f"{meta_prefix} · {project_title(project_dir.name, titles)}",
                        "src": rel(web),
                        "project": project_dir.name,
                    }
                )

    if allow_video:
        videos = list_files(project_dir, VID_EXT)
        by_stem: dict[str, Path] = {}
        for v in videos:
            s = v.stem.lower()
            if s not in by_stem or v.suffix.lower() == ".mp4":
                by_stem[s] = v
        for i, vid in enumerate(by_stem.values()):
            size_mb = vid.stat().st_size / (1024 * 1024)
            if size_mb > 40:
                print(f"  ⚠ 视频偏大 {vid.name} ≈ {size_mb:.0f}MB")

            # 自动补封面（缺则截帧）
            cover = ensure_video_cover(
                vid,
                project_dir,
                also_project_cover=(i == 0 or not (project_dir / "cover.jpg").exists()),
            )
            # 刷新 image_map（可能刚生成封面）
            images = list_files(project_dir, IMG_EXT)
            image_map = {p.stem.lower(): p for p in images}
            if cover is None:
                for key in ("cover", "poster", f"{vid.stem}-cover", f"{vid.stem}_cover", vid.stem):
                    if key.lower() in image_map:
                        cover = image_map[key.lower()]
                        break

            entry = {
                "id": slug_id(cat, project_dir.name, vid.stem),
                "cat": cat,
                "type": "video",
                "title": stem_title(vid.name, titles),
                "meta": f"{meta_prefix} · {project_title(project_dir.name, titles)}",
                "src": rel(vid),
                "project": project_dir.name,
            }
            if cover:
                if cover.stat().st_size > 500_000 or cover.suffix.lower() == ".png":
                    w = ensure_web_image(cover, web_dir)
                    entry["cover"] = rel(w) if w else rel(cover)
                else:
                    entry["cover"] = rel(cover)
            else:
                print(f"  ⚠ 未能生成封面: {vid.name}")
            items.append(entry)
            print(f"  视频 {project_dir.name}/{vid.name}")

    if not items:
        return None

    # 项目封面：优先 cover.jpg；否则首条视频封面/首图
    cover = None
    for cand in (
        project_dir / "cover.jpg",
        project_dir / "cover.png",
        project_dir / "web" / "cover.jpg",
    ):
        if cand.exists():
            if cand.suffix.lower() != ".jpg":
                w = ensure_web_image(cand, web_dir)
                cover = rel(w) if w else rel(cand)
            else:
                cover = rel(cand)
            break
    if not cover:
        for it in items:
            if it.get("cover"):
                cover = it["cover"]
                break
            if it["type"] == "image":
                cover = it["src"]
                break
    if not cover:
        cover = items[0].get("cover") or items[0]["src"]
    # 若仍无项目 cover.jpg 且有视频封面，落一份 cover.jpg
    project_cover_path = project_dir / "cover.jpg"
    if not project_cover_path.exists():
        for it in items:
            if it.get("cover"):
                src_c = ROOT / it["cover"]
                if src_c.exists():
                    import shutil
                    try:
                        shutil.copy2(src_c, project_cover_path)
                        cover = rel(project_cover_path)
                    except Exception:
                        pass
                break

    return {
        "id": slug_id("photo", project_dir.name),
        "folder": project_dir.name,
        "cat": cat,
        "title": project_title(project_dir.name, titles),
        "cover": cover,
        "count": len(items),
        "items": items,
    }


def collect_featured_photo_projects(titles: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """
    精选三栏：每个栏位下可有多个「子项目」文件夹。
    结构：
      photo/港湾日光/芒果/*.jpg
      photo/港湾日光/胖胖/*.jpg
      photo/城市追光/沿海公路/*.mp4

    散落在栏位根目录的文件会自动归入「未分组」子项目。
    返回 (PHOTO_PROJECTS, flat works, FEATURED_PROJECTS)
    """
    base = ROOT / "assets/portfolio/photo"
    base.mkdir(parents=True, exist_ok=True)
    photo_projects: list[dict] = []
    flat: list[dict] = []
    featured: list[dict] = []

    meta_map = {
        "film": "摄影约拍 · 动态跟拍",
        "moto-night": "摄影约拍 · 夜间素材",
        "moto-day": "摄影约拍 · 日间素材",
    }

    for slot in FEATURED_SLOTS:
        slot_dir = base / slot["folder"]
        slot_dir.mkdir(parents=True, exist_ok=True)

        if slot["folder"] == "城市追光":
            allow_video, allow_image = True, True
        elif slot["folder"] in ("夜色锋芒", "港湾日光"):
            allow_video, allow_image = False, True
        else:
            allow_video = slot["kind"] == "video"
            allow_image = slot["kind"] == "image"

        print(f"\n扫描精选栏「{slot['folder']}」…")

        # 根目录散落媒体 → 归入「未分组」
        loose = []
        for f in list_files(slot_dir, IMG_EXT | VID_EXT):
            if is_cover_file(f) or f.stem.lower() in COVER_NAMES:
                continue
            loose.append(f)
        if loose:
            ungrouped = slot_dir / "未分组"
            ungrouped.mkdir(exist_ok=True)
            for f in loose:
                dest = ungrouped / f.name
                if not dest.exists():
                    f.rename(dest)
                    print(f"  归入: {f.name} → {slot['folder']}/未分组/")

        slot_projects: list[dict] = []
        for sub in project_dirs(slot_dir):
            # 跳过空 web 目录
            if sub.name == "web":
                continue
            proj = collect_media_project(
                sub,
                cat=slot["cat"],
                meta_prefix=meta_map.get(slot["cat"], "摄影约拍"),
                titles=titles,
                allow_video=allow_video,
                allow_image=allow_image,
            )
            if not proj:
                continue
            # 标注所属精选栏
            proj["slot"] = slot["folder"]
            proj["id"] = slug_id("photo", slot["folder"], sub.name)
            proj["folder"] = sub.name  # 子项目名
            proj["path"] = f"{slot['folder']}/{sub.name}"
            for it in proj["items"]:
                it["slot"] = slot["folder"]
                it["project"] = sub.name
            slot_projects.append(proj)
            photo_projects.append(proj)
            flat.extend(proj["items"])
            print(f"  项目「{proj['title']}」× {proj['count']}")

        if not slot_projects:
            print("  → 暂无子项目。请在该栏下新建文件夹并放入作品。")

        # 精选大卡预览：优先栏位 cover.jpg，否则第一个项目封面/视频
        card_type = "image"
        card_src = ""
        card_cover = ""
        slot_cover = slot_dir / "cover.jpg"
        if slot_cover.exists():
            card_src = rel(slot_cover)
            card_cover = card_src
        if slot_projects:
            first = slot_projects[0]
            if slot["kind"] == "video":
                vids = [i for p in slot_projects for i in p["items"] if i["type"] == "video"]
                if vids:
                    card_type = "video"
                    card_src = vids[0]["src"]
                    card_cover = vids[0].get("cover") or first["cover"] or card_cover
                elif not card_src:
                    card_src = first["cover"]
                    card_cover = first["cover"]
            elif not card_src:
                card_src = first["cover"]
                card_cover = first["cover"]

        featured.append(
            {
                "id": f"slot-{slot['folder']}",
                "number": slot["number"],
                "layout": slot["layout"],
                "type": card_type,
                "label": slot["label"],
                "title": titles.get(slot["folder"] + "_title", slot["title"]),
                "subtitle": slot["subtitle"],
                "src": card_src,
                "cover": card_cover or card_src,
                "open": f"photo-slot:{slot['folder']}",
                "folder": slot["folder"],
                "projectCount": len(slot_projects),
            }
        )

    return photo_projects, flat, featured


# ── AIGC（沿用项目结构）──────────────────────────────────


def project_dirs(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return [
        p
        for p in sorted(base.iterdir())
        if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_DIR_NAMES
    ]


def collect_aigc(titles: dict) -> tuple[list[dict], list[dict]]:
    projects: list[dict] = []
    flat: list[dict] = []
    design_base = ROOT / "assets/portfolio/aigc/design"
    video_base = ROOT / "assets/portfolio/aigc/video"
    design_base.mkdir(parents=True, exist_ok=True)
    video_base.mkdir(parents=True, exist_ok=True)

    # 散落单文件自动归入同名项目
    for base, is_vid in ((design_base, False), (video_base, True)):
        for f in list_files(base, VID_EXT if is_vid else IMG_EXT):
            if is_cover_file(f):
                continue
            dest_dir = base / f.stem
            if not dest_dir.exists():
                dest_dir.mkdir(parents=True, exist_ok=True)
                print(f"  归入项目: {f.name} → {dest_dir.relative_to(ROOT)}/")
                f.rename(dest_dir / f.name)

    print("\n扫描 AI 设计项目…")
    for d in project_dirs(design_base):
        proj = collect_media_project(
            d, "ai-design", "AIGC · AI 设计", titles, allow_video=False, allow_image=True
        )
        if proj:
            projects.append(proj)
            flat.extend(proj["items"])
            print(f"  design「{proj['title']}」× {proj['count']}")

    print("\n扫描 AI 视频项目…")
    for d in project_dirs(video_base):
        proj = collect_media_project(
            d, "ai-video", "AIGC · AI 视频", titles, allow_video=True, allow_image=True
        )
        if proj:
            # 去掉纯封面类 image 误登记：视频项目里若有 image 且不是主要作品可保留
            projects.append(proj)
            flat.extend(proj["items"])
            print(f"  video「{proj['title']}」× {proj['count']}")

    return projects, flat


# ── 写 works.js ─────────────────────────────────────────


def render_projects_array(name: str, projects: list[dict]) -> str:
    lines = [f"window.{name} = ["]
    for p in projects:
        lines.append("  {")
        for key in ("id", "folder", "path", "slot", "cat", "title", "cover"):
            if key in p and p[key] is not None:
                lines.append(f"    {key}: {js_string(p[key])},")
        lines.append(f"    count: {int(p.get('count', 0))},")
        lines.append("    items: [")
        for it in p.get("items") or []:
            lines.append(render_item(it, 6))
        lines.append("    ],")
        lines.append("  },")
    lines.append("];")
    return "\n".join(lines)


def render_featured(featured: list[dict]) -> str:
    lines = ["window.FEATURED_PROJECTS = ["]
    for f in featured:
        lines.append("  {")
        for key in (
            "id",
            "number",
            "layout",
            "type",
            "label",
            "title",
            "subtitle",
            "src",
            "cover",
            "open",
            "folder",
        ):
            if key in f and f[key] not in (None, ""):
                lines.append(f"    {key}: {js_string(str(f[key]))},")
        lines.append("  },")
    lines.append("];")
    return "\n".join(lines)


def render_portfolio_works(items: list[dict]) -> str:
    lines = ["window.PORTFOLIO_WORKS = ["]
    for it in items:
        lines.append(render_item(it, 2))
    lines.append("];")
    return "\n".join(lines)


CATEGORIES_BLOCK = """
window.PORTFOLIO_CATEGORIES = {
  all: { label: "全部", parent: null },
  photo: { label: "摄影约拍", parent: null, children: ["film", "moto-night", "moto-day"] },
  film: { label: "城市追光 · 动态跟拍", parent: "photo", empty: "请往 photo/城市追光/ 上传跟拍视频。" },
  "moto-night": { label: "夜色锋芒 · 夜间素材", parent: "photo", empty: "请往 photo/夜色锋芒/ 上传夜景作品。" },
  "moto-day": { label: "港湾日光 · 日间素材", parent: "photo", empty: "请往 photo/港湾日光/ 上传日间作品。" },
  aigc: { label: "AIGC 作品", parent: null, children: ["ai-video", "ai-design"] },
  "ai-video": { label: "AI 视频", parent: "aigc", empty: "AI 视频项目陆续更新中。" },
  "ai-design": { label: "AI 设计", parent: "aigc", empty: "AI 设计项目陆续更新中。" },
};
""".strip()


def extract_block(text: str, start_marker: str) -> str | None:
    i = text.find(start_marker)
    if i < 0:
        return None
    eq = text.find("=", i)
    j = eq + 1
    while j < len(text) and text[j] in " \t\n\r":
        j += 1
    if j >= len(text) or text[j] not in "[{":
        return None
    open_ch = text[j]
    close_ch = "]" if open_ch == "[" else "}"
    depth = 0
    k = j
    in_str = False
    str_ch = ""
    escape = False
    while k < len(text):
        ch = text[k]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == str_ch:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                str_ch = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    end = k + 1
                    if end < len(text) and text[end] == ";":
                        end += 1
                    return text[i:end]
        k += 1
    return None


def rebuild_works_js(
    works: list[dict],
    photo_projects: list[dict],
    aigc_projects: list[dict],
    featured: list[dict],
) -> None:
    old = WORKS_JS.read_text(encoding="utf-8") if WORKS_JS.exists() else ""
    aigc_home = extract_block(old, "window.AIGC_HOME")
    if not aigc_home:
        aigc_home = """window.AIGC_HOME = {
  kicker: "GENERATIVE / MOTION / DESIGN",
  title: "AIGC",
  titleEm: "作品集",
  intro: "按项目浏览 AI 视频与 AI 设计。",
  cover: "assets/portfolio/aigc/aigc-section-cover.jpg",
  categories: [
    { num: "01", en: "AI MOTION", title: "AI 视频作品", desc: "按项目查看动态影像。", filter: "ai-video" },
    { num: "02", en: "AI DESIGN", title: "AI 设计作品", desc: "按项目查看设计内容。", filter: "ai-design" },
  ],
};"""

    header = """/**
 * 营口机车影像 · 作品数据（sync-works.py 自动生成）
 * -------------------------------------------------------
 * 精选三栏项目文件夹：
 *   assets/portfolio/photo/城市追光/   动态跟拍视频
 *   assets/portfolio/photo/夜色锋芒/   夜间拍摄素材
 *   assets/portfolio/photo/港湾日光/   白天拍摄素材
 *
 * AIGC：
 *   assets/portfolio/aigc/video/项目名/
 *   assets/portfolio/aigc/design/项目名/
 *
 * 双击「更新作品.command」同步。改标题见 titles.json。
 */
"""
    body = "\n\n".join(
        [
            header.strip(),
            render_featured(featured),
            aigc_home.strip(),
            render_projects_array("PHOTO_PROJECTS", photo_projects),
            render_projects_array("AIGC_PROJECTS", aigc_projects),
            render_portfolio_works(works),
            CATEGORIES_BLOCK,
            "",
        ]
    )
    WORKS_JS.write_text(body, encoding="utf-8")
    print(
        f"\n✓ works.js 已更新：摄影项目 {len(photo_projects)} · AIGC 项目 {len(aigc_projects)} · 作品 {len(works)}"
    )


def ensure_titles() -> None:
    if TITLES_JSON.exists():
        return
    sample = {
        "_说明": "键=项目文件夹名或文件名，值=展示标题",
        "城市追光": "城市追光",
        "夜色锋芒": "夜色锋芒",
        "港湾日光": "港湾日光",
        "莫奈营口": "莫奈营口",
        "彩妆广告": "彩妆广告",
        "疯狂的麦克斯-狂暴营口": "疯狂的麦克斯 · 狂暴营口",
    }
    TITLES_JSON.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    print("=== 营口机车影像 · 同步作品 ===")
    print(f"目录: {ROOT}")
    ensure_titles()

    # 1) 先规范命名（DSC / ChatGPT / grok-video…）
    run_auto_rename_all()

    # 2) 再扫描入库
    titles = load_titles()
    photo_projects, photo_flat, featured = collect_featured_photo_projects(titles)
    aigc_projects, aigc_flat = collect_aigc(titles)
    works = photo_flat + aigc_flat
    rebuild_works_js(works, photo_projects, aigc_projects, featured)

    print("\n精选项目：")
    for f in featured:
        print(f"  {f['number']} {f['folder']} → open={f['open']} type={f['type']}")
    print("\n完成。刷新浏览器（Cmd+Shift+R）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
