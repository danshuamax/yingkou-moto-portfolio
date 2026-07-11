(() => {
  const worksData = window.PORTFOLIO_WORKS || [];
  const categories = window.PORTFOLIO_CATEGORIES || {};
  const featuredProjects = window.FEATURED_PROJECTS || [];
  const aigcHome = window.AIGC_HOME || null;
  const aigcProjects = window.AIGC_PROJECTS || [];
  const photoProjects = window.PHOTO_PROJECTS || [];

  const header = document.querySelector(".site-header");
  const nav = document.getElementById("nav");
  const navToggle = document.getElementById("navToggle");
  const yearEl = document.getElementById("year");
  const projectGrid = document.getElementById("projectGrid");
  const aigcHomeCover = document.getElementById("aigcHomeCover");
  const projectBrowser = document.getElementById("projectBrowser");
  const pbGrid = document.getElementById("pbGrid");
  const pbTitle = document.getElementById("pbTitle");
  const pbKicker = document.getElementById("pbKicker");
  const pbEmpty = document.getElementById("pbEmpty");
  const pbClose = document.getElementById("pbClose");
  const lightbox = document.getElementById("lightbox");
  const lbMedia = document.getElementById("lbMedia");
  const lbTitle = document.getElementById("lbTitle");
  const lbMeta = document.getElementById("lbMeta");
  const lbClose = document.getElementById("lbClose");
  const lbPrev = document.getElementById("lbPrev");
  const lbNext = document.getElementById("lbNext");
  const form = document.getElementById("contactForm");
  const formNote = document.getElementById("formNote");

  /** @type {any[]} */
  let lightboxList = [];
  let currentIndex = 0;

  if (yearEl) yearEl.textContent = String(new Date().getFullYear());

  // —— Header ——
  const onScroll = () => {
    header?.classList.toggle("is-scrolled", window.scrollY > 24);
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  navToggle?.addEventListener("click", () => {
    const open = navToggle.getAttribute("aria-expanded") === "true";
    navToggle.setAttribute("aria-expanded", String(!open));
    nav?.classList.toggle("is-open", !open);
  });

  nav?.querySelectorAll("a").forEach((a) => {
    a.addEventListener("click", () => {
      nav.classList.remove("is-open");
      navToggle?.setAttribute("aria-expanded", "false");
    });
  });

  // —— 分类匹配（灯箱浏览用）——
  function matchFilter(workCat, filter) {
    if (filter === "all") return true;
    if (filter === "photo") {
      return (
        workCat === "film" ||
        workCat === "moto" ||
        workCat === "moto-night" ||
        workCat === "moto-day"
      );
    }
    if (filter === "aigc") return workCat === "ai-video" || workCat === "ai-design";
    return workCat === filter;
  }

  function worksByCat(filter) {
    return worksData.filter((w) => matchFilter(w.cat, filter));
  }

  // —— 精选项目大卡 ——
  function renderFeaturedProjects() {
    if (!projectGrid) return;
    projectGrid.innerHTML = "";

    featuredProjects.forEach((proj) => {
      const card = document.createElement("article");
      card.className =
        "project-card" + (proj.layout === "wide" ? " project-card--wide" : "");
      card.tabIndex = 0;
      card.setAttribute("role", "button");
      card.setAttribute("aria-label", `${proj.title} · ${proj.subtitle || ""}`);

      if (proj.type === "video") {
        const video = document.createElement("video");
        video.src = proj.src;
        video.muted = true;
        video.loop = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute("playsinline", "");
        video.preload = "metadata";
        if (proj.cover) video.poster = proj.cover;
        video.className = "project-video";
        video.setAttribute("aria-hidden", "true");
        card.appendChild(video);
      } else {
        const img = document.createElement("img");
        img.src = proj.src;
        img.alt = proj.title || "";
        img.loading = "lazy";
        card.appendChild(img);
      }

      card.insertAdjacentHTML(
        "beforeend",
        `
        <div class="project-shade" aria-hidden="true"></div>
        <span class="project-number">${escapeHtml(proj.number || "")}</span>
        <div class="project-info">
          <p>${escapeHtml(proj.label || "")}</p>
          <h3>${escapeHtml(proj.title || "")}</h3>
          <span>${escapeHtml(proj.subtitle || "")}</span>
        </div>
        <span class="project-arrow" aria-hidden="true"><span>↗</span></span>
      `
      );

      const activate = () => handleProjectOpen(proj);
      card.addEventListener("click", activate);
      card.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });

      projectGrid.appendChild(card);
    });

    setupProjectVideoObserver();
  }

  function findPhotoProject(folderOrId) {
    return (
      photoProjects.find(
        (p) =>
          p.folder === folderOrId ||
          p.id === folderOrId ||
          p.path === folderOrId
      ) || null
    );
  }

  /** 打开精选栏下的「项目列表」（与 AIGC 相同卡片格式） */
  function openPhotoSlot(slotName) {
    const projects = photoProjects.filter((p) => p.slot === slotName);
    if (!projects.length) {
      alert(
        `「${slotName}」里还没有项目。\n\n上传方式：\nassets/portfolio/photo/${slotName}/项目名称/\n放入照片或视频后，运行「更新作品」。`
      );
      return;
    }
    openProjectBrowser({
      source: "photo",
      slot: slotName,
      projects,
    });
  }

  function openPhotoProject(folderOrId) {
    // 若传入的是精选栏名，打开项目列表
    const asSlot = photoProjects.filter((p) => p.slot === folderOrId);
    if (asSlot.length) {
      openPhotoSlot(folderOrId);
      return;
    }
    const proj = findPhotoProject(folderOrId);
    if (!proj || !(proj.items || []).length) {
      alert(
        `「${folderOrId}」里还没有作品。\n请把文件放进对应项目文件夹后运行「更新作品」。`
      );
      return;
    }
    openLightboxFromList(proj.items, 0);
  }

  function handleProjectOpen(proj) {
    const open = proj.open || "lightbox";
    if (open.startsWith("photo-slot:")) {
      openPhotoSlot(open.slice("photo-slot:".length));
      return;
    }
    if (open.startsWith("photo-project:")) {
      // 兼容旧数据：栏位名 → 项目列表
      openPhotoSlot(open.slice("photo-project:".length));
      return;
    }
    if (open.startsWith("cat:")) {
      openCategoryLightbox(open.slice(4));
      return;
    }
    if (open === "lightbox") {
      if (proj.folder) {
        openPhotoSlot(proj.folder);
        return;
      }
      if (proj.workId) {
        openWorkById(proj.workId);
      } else if (proj.src) {
        openLightboxFromList(
          [
            {
              id: proj.id,
              type: proj.type,
              title: proj.title,
              meta: proj.subtitle,
              src: proj.src,
              cover: proj.cover,
              cat: "film",
            },
          ],
          0
        );
      }
    }
  }

  function openCategoryLightbox(cat) {
    const projects = aigcProjects.filter((p) => matchFilter(p.cat, cat));
    if (projects.length) {
      openProjectBrowser({ source: "aigc", cat, projects });
      return;
    }
    const list = worksByCat(cat);
    if (!list.length) return;
    openLightboxFromList(list, 0);
  }

  /**
   * 项目浏览器（摄影精选 / AIGC 共用）
   * opts: { source, slot?, cat?, projects? }
   */
  function openProjectBrowser(opts) {
    if (!projectBrowser || !pbGrid) return;
    const options =
      typeof opts === "string"
        ? { source: "aigc", cat: opts }
        : opts || { source: "aigc", cat: "aigc" };

    let projects = options.projects;
    if (!projects) {
      if (options.source === "photo") {
        projects = options.slot
          ? photoProjects.filter((p) => p.slot === options.slot)
          : photoProjects.slice();
      } else {
        const cat = options.cat || "aigc";
        projects =
          cat === "aigc" || cat === "all"
            ? aigcProjects.slice()
            : aigcProjects.filter((p) => p.cat === cat);
      }
    }

    const photoKickers = {
      城市追光: "CITY CHASE · FILM",
      夜色锋芒: "NIGHT EDGE · SHOOT",
      港湾日光: "HARBOR LIGHT · SHOOT",
    };
    const aigcKickers = {
      "ai-video": "AI MOTION",
      "ai-design": "AI DESIGN",
      aigc: "AIGC PROJECTS",
    };
    const aigcTitles = {
      "ai-video": "AI 视频项目",
      "ai-design": "AI 设计项目",
      aigc: "全部 AIGC 项目",
    };

    if (options.source === "photo") {
      if (pbKicker) pbKicker.textContent = photoKickers[options.slot] || "PHOTO PROJECTS";
      if (pbTitle) pbTitle.textContent = `${options.slot || "摄影"} · 项目列表`;
    } else {
      const cat = options.cat || "aigc";
      if (pbKicker) pbKicker.textContent = aigcKickers[cat] || "AIGC PROJECTS";
      if (pbTitle) pbTitle.textContent = aigcTitles[cat] || "项目列表";
    }

    pbGrid.innerHTML = "";
    if (pbEmpty) pbEmpty.hidden = projects.length > 0;

    const badgeFor = (proj) => {
      if (proj.cat === "ai-video" || proj.cat === "film") return "视频";
      if (proj.cat === "ai-design") return "设计";
      if (proj.cat === "moto-night") return "夜景";
      if (proj.cat === "moto-day") return "日间";
      return "作品";
    };

    projects.forEach((proj) => {
      const card = document.createElement("button");
      card.type = "button";
      card.className = "pb-card";
      const n = proj.count || (proj.items || []).length;
      const cover =
        proj.cover ||
        (proj.items && proj.items[0] && (proj.items[0].cover || proj.items[0].src)) ||
        "";
      card.innerHTML = `
        <div class="pb-card-media">
          ${
            proj.items &&
            proj.items[0] &&
            proj.items[0].type === "video" &&
            !proj.cover
              ? `<video src="${escapeAttr(proj.items[0].src)}" muted loop playsinline preload="metadata"></video>`
              : `<img src="${escapeAttr(cover)}" alt="" loading="lazy" />`
          }
          <span class="pb-card-badge">${badgeFor(proj)} · ${n} 件</span>
        </div>
        <div class="pb-card-body">
          <strong>${escapeHtml(proj.title || proj.folder || "")}</strong>
          <span>点击查看项目内容 ↗</span>
        </div>
      `;
      card.addEventListener("click", () => {
        const items = proj.items || [];
        if (!items.length) return;
        closeProjectBrowser();
        openLightboxFromList(items, 0);
      });
      pbGrid.appendChild(card);
    });

    projectBrowser.hidden = false;
    document.body.style.overflow = "hidden";

    // 预览视频自动播放
    pbGrid.querySelectorAll("video").forEach((v) => {
      v.muted = true;
      v.play().catch(() => {});
    });
  }

  function closeProjectBrowser() {
    if (!projectBrowser) return;
    projectBrowser.hidden = true;
    if (lightbox?.hidden !== false) {
      document.body.style.overflow = "";
    }
  }

  function renderAigcHome() {
    if (!aigcHomeCover || !aigcHome) return;
    aigcHomeCover.innerHTML = "";

    if (aigcHome.cover) {
      const img = document.createElement("img");
      img.className = "aigc-bg";
      img.src = aigcHome.cover;
      img.alt = "";
      aigcHomeCover.appendChild(img);
    }
    const overlay = document.createElement("div");
    overlay.className = "film-overlay";
    overlay.setAttribute("aria-hidden", "true");
    aigcHomeCover.appendChild(overlay);

    const list = document.createElement("div");
    list.className = "aigc-category-list";
    (aigcHome.categories || []).forEach((cat) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "aigc-category-card";
      const count = aigcProjects.filter((p) => p.cat === cat.filter).length;
      btn.innerHTML = `
        <span>${escapeHtml(cat.num)}</span>
        <div>
          <p>${escapeHtml(cat.en)}</p>
          <h3>${escapeHtml(cat.title)}</h3>
          <small>${escapeHtml(cat.desc)}${count ? ` · ${count} 个项目` : ""}</small>
        </div>
        <b aria-hidden="true">↗</b>
      `;
      btn.addEventListener("click", () =>
        openProjectBrowser({ source: "aigc", cat: cat.filter || "aigc" })
      );
      list.appendChild(btn);
    });
    aigcHomeCover.appendChild(list);

    document.getElementById("aigcBrowseAll")?.addEventListener("click", () => {
      openProjectBrowser({ source: "aigc", cat: "aigc" });
    });

    pbClose?.addEventListener("click", closeProjectBrowser);
    projectBrowser?.addEventListener("click", (e) => {
      if (e.target === projectBrowser) closeProjectBrowser();
    });
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && projectBrowser && !projectBrowser.hidden) {
        closeProjectBrowser();
      }
    });
  }

  let projectVideoIo = null;

  function pauseAllPreviews() {
    projectGrid?.querySelectorAll("video").forEach((v) => v.pause());
  }

  function setupProjectVideoObserver() {
    if (projectVideoIo) {
      projectVideoIo.disconnect();
      projectVideoIo = null;
    }
    const videos = projectGrid?.querySelectorAll("video") || [];
    if (!videos.length) return;
    if (!("IntersectionObserver" in window)) {
      videos.forEach((v) => v.play().catch(() => {}));
      return;
    }
    projectVideoIo = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const video = entry.target;
          if (!(video instanceof HTMLVideoElement)) return;
          if (lightbox && !lightbox.hidden) {
            video.pause();
            return;
          }
          if (entry.isIntersecting) video.play().catch(() => {});
          else video.pause();
        });
      },
      { threshold: 0.25 }
    );
    videos.forEach((v) => projectVideoIo.observe(v));
  }

  function categoryLabel(cat) {
    return (categories[cat] && categories[cat].label) || cat;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  // 套餐按钮：跳转预约并预选意向
  document.querySelectorAll("[data-package]").forEach((el) => {
    el.addEventListener("click", () => {
      const pkg = el.getAttribute("data-package");
      const select = document.getElementById("type");
      if (pkg && select) {
        select.value = pkg;
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
    });
  });

  // —— Lightbox ——
  function openWorkById(id) {
    const idx = worksData.findIndex((w) => w.id === id);
    if (idx < 0) {
      openLightboxFromList(worksData, 0);
      return;
    }
    openLightboxFromList(worksData, idx);
  }

  function openLightboxFromList(list, index) {
    if (!list.length) return;
    lightboxList = list;
    currentIndex = ((index % list.length) + list.length) % list.length;
    const work = list[currentIndex];

    pauseAllPreviews();

    lbMedia.innerHTML = "";
    if (work.type === "video") {
      const video = document.createElement("video");
      video.src = work.src;
      video.controls = true;
      video.autoplay = true;
      video.playsInline = true;
      video.muted = false;
      video.poster = work.cover || "";
      video.className = "lb-video";
      lbMedia.appendChild(video);
    } else {
      const img = document.createElement("img");
      img.src = work.src;
      img.alt = work.title || "";
      img.id = "lbImg";
      lbMedia.appendChild(img);
    }

    lbTitle.textContent = work.title || "";
    lbMeta.textContent = work.meta || categoryLabel(work.cat);
    lightbox.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeLightbox() {
    lbMedia.querySelectorAll("video").forEach((v) => {
      v.pause();
      v.removeAttribute("src");
      v.load();
    });
    lbMedia.innerHTML = "";
    lightbox.hidden = true;
    document.body.style.overflow = "";
    setupProjectVideoObserver();
  }

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      pauseAllPreviews();
    } else if (!lightbox || lightbox.hidden) {
      setupProjectVideoObserver();
    }
  });

  lbClose?.addEventListener("click", closeLightbox);
  lbPrev?.addEventListener("click", () =>
    openLightboxFromList(lightboxList.length ? lightboxList : worksData, currentIndex - 1)
  );
  lbNext?.addEventListener("click", () =>
    openLightboxFromList(lightboxList.length ? lightboxList : worksData, currentIndex + 1)
  );
  lightbox?.addEventListener("click", (e) => {
    if (e.target === lightbox) closeLightbox();
  });

  window.addEventListener("keydown", (e) => {
    if (lightbox?.hidden) return;
    if (e.key === "Escape") closeLightbox();
    const list = lightboxList.length ? lightboxList : worksData;
    if (e.key === "ArrowLeft") openLightboxFromList(list, currentIndex - 1);
    if (e.key === "ArrowRight") openLightboxFromList(list, currentIndex + 1);
  });

  // —— 表单 ——
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    const data = new FormData(form);
    const name = String(data.get("name") || "").trim();
    const channel = String(data.get("channel") || "").trim();
    const type = String(data.get("type") || "");
    const msg = String(data.get("msg") || "").trim();

    if (!name || !channel) {
      formNote.textContent = "请至少填写称呼与联系方式。";
      formNote.classList.remove("is-ok");
      return;
    }

    const typeMap = {
      "moto-299": "单人机车写真 · ¥299（约1.5小时 / 12张精修 / 1场景1造型）",
      "film-499": "电影感机车短片 · ¥499（15-30秒 / 脚本分镜 / 竖横二选一）",
      "combo-799": "影像故事组合 · ¥799（18张精修 / 30-45秒短片 / 双场景）",
      "ai-video": "AIGC · AI 视频作品",
      "ai-design": "AIGC · AI 设计作品",
      other: "其他合作 / 定制",
    };

    const subject = encodeURIComponent(`[营口机车影像] ${typeMap[type] || type} - ${name}`);
    const body = encodeURIComponent(
      `称呼：${name}\n联系方式：${channel}\n意向类型：${typeMap[type] || type}\n\n需求简述：\n${msg || "（未填写）"}\n`
    );

    window.location.href = `mailto:15541719527@139.com?subject=${subject}&body=${body}`;
    formNote.textContent = "已尝试打开邮件客户端。若未弹出，请直接微信联系 jun365050207。";
    formNote.classList.add("is-ok");
  });

  // —— 拍摄日志 ——
  function renderJournal() {
    const list = document.getElementById("journalList");
    const entries = window.JOURNAL_ENTRIES || [];
    if (!list) return;
    list.innerHTML = "";

    if (!entries.length) {
      list.innerHTML =
        '<p class="gallery-empty">拍摄日志即将更新，敬请期待。</p>';
      return;
    }

    entries.forEach((entry) => {
      const isLink = Boolean(entry.link);
      const el = document.createElement(isLink ? "a" : "article");
      el.className = "journal-card";
      if (isLink) {
        el.href = entry.link;
      }

      const coverHtml = entry.cover
        ? `<div class="journal-cover"><img src="${escapeAttr(entry.cover)}" alt="" loading="lazy" /></div>`
        : `<div class="journal-cover"></div>`;

      el.innerHTML = `
        ${coverHtml}
        <div class="journal-body">
          <div class="journal-meta">
            <span class="journal-date">${escapeHtml(entry.date || "")}</span>
            <span class="journal-tag">${escapeHtml(entry.tag || "")}</span>
          </div>
          <h3>${escapeHtml(entry.title || "")}</h3>
          <p>${escapeHtml(entry.excerpt || "")}</p>
          ${isLink ? '<span class="journal-more">查看相关 →</span>' : ""}
        </div>
      `;
      list.appendChild(el);
    });
  }

  // —— 滚动显现 ——
  function setupReveal() {
    const revealTargets = document.querySelectorAll(
      ".section-head, .work-heading, .project-card, .aigc-home, .price-card, .about-visual, .about-copy, .journal-card, .contact-item, .contact-form"
    );
    revealTargets.forEach((el) => el.classList.add("reveal"));

    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) {
              entry.target.classList.add("is-in");
              io.unobserve(entry.target);
            }
          });
        },
        { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
      );
      revealTargets.forEach((el) => io.observe(el));
    } else {
      revealTargets.forEach((el) => el.classList.add("is-in"));
    }
  }

  renderFeaturedProjects();
  renderAigcHome();
  renderJournal();
  setupReveal();
})();
