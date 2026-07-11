/**
 * 营口机车影像 · 拍摄日志
 * -------------------------------------------------------
 * 之后更新日志：在本数组顶部追加一条即可（新在前）。
 *
 * 字段说明：
 *   id      — 唯一标识
 *   date    — 日期文案，如 "2026.07"
 *   tag     — 标签：机车写真 / 电影感短片 / AIGC / 活动 等
 *   title   — 标题
 *   excerpt — 摘要正文
 *   cover   — 可选封面图路径
 *   link    — 可选，跳转到作品集筛选等，如 "#portfolio"
 */
window.JOURNAL_ENTRIES = [
  {
    id: "log-2026-07-film",
    date: "2026.07",
    tag: "电影感短片",
    title: "黄昏公路 · 跟拍成片上线",
    excerpt:
      "竖屏跟拍短片入库作品集。逆光下的机车轮廓、道路延展与节奏剪辑，作为「电影感机车短片」方向的样片展示。点击作品集可直接观看动态预览。",
    cover: "assets/portfolio/photo/film/moto-film-01-cover.jpg",
    link: "#portfolio",
  },
  {
    id: "log-2026-07-hero",
    date: "2026.07",
    tag: "AIGC · 主视觉",
    title: "潮流涂鸦主视觉上线首页",
    excerpt:
      "骑士坐姿人像结合涂鸦龙纹与卡通元素，作为站点首页主视觉。真实拍摄与生成设计混搭，延续「机车影像 + AIGC」的品牌表达。",
    cover: "assets/brand/hero-home.jpg",
    link: "#top",
  },
  {
    id: "log-night-moto",
    date: "近期",
    tag: "单人机车写真",
    title: "海岸线夜骑 · 铬光与黄标",
    excerpt:
      "夜景机位下的哈雷与骑士人像：黄标指示牌、海风与金属反光。这组写真构成作品集「单人机车写真」的核心样张，也是约拍套餐的风格参考。",
    cover: "assets/portfolio/photo/moto/web/DSC06875.jpg",
    link: "#portfolio",
  },
  {
    id: "log-harbor-day",
    date: "2026.07",
    tag: "单人机车写真",
    title: "港湾日光 · 公路约拍成片入库",
    excerpt:
      "日间沿海与港区机位新一组写真已完成压缩并登记上线。弯标、双圆灯与斑马线低角度构成「日间约拍」方向的核心样张。",
    cover: "assets/portfolio/photo/moto/web/DSC08845.jpg",
    link: "#portfolio",
  },
];
