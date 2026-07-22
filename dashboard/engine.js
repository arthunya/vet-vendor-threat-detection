/* V.E.T. risk engine — JavaScript port (demo calibration v0.2)
   Ported from vet/engine.py + vet/features/*. Runs entirely client-side so
   the dashboard's "system checks in ~2 seconds" step performs REAL
   computation: fuzzy sanctions matching, containment detection, weighted
   ensemble with renormalization, and the CRITICAL override.
   Differences from the Python Phase-1 engine are calibration-only and are
   documented in the dashboard methodology section. */

(function (g) {
  "use strict";

  const HIGH_J = new Set(["IR", "KP", "SY", "CU", "RU", "BY", "MM"]);
  const GREY_J = new Set(["DZ", "AO", "CI", "CD", "HT", "KE", "LB", "MC", "MZ",
    "NA", "NP", "NG", "ZA", "SS", "VE", "VN", "YE", "LA", "BG"]);
  const SUFFIX = new Set(["CO", "LTD", "INC", "CORP", "CORPORATION", "COMPANY",
    "LLC", "PLC", "OAO", "PAO", "OJSC", "PJSC", "AO", "OU", "GMBH", "SA", "AG",
    "PTE", "SDN", "BHD", "LIMITED", "INCORPORATED", "SYNTHETIC", "DEMO"]);
  const DUAL_USE = ["3341", "3344", "3345", "3364", "3329", "4236", "4239"];
  const DIVERSION_LOGISTICS = ["4885", "4931"];
  const FIN_CACHE = { "0000320193": { ratio: 0.21, fy: "FY2025" },
                      "0001286681": { ratio: -2.27, fy: "FY2025" } };
  const WEIGHTS = { sanctions: 0.35, financial: 0.15, geographic: 0.15,
                    opacity: 0.20, industry: 0.15 };

  function normalize(s) {
    return s.toUpperCase().replace(/[,.()\[\]&\/\-']/g, " ")
            .replace(/\s+/g, " ").trim();
  }
  function stripSuffix(s) {
    const t = s.split(" ").filter(x => !SUFFIX.has(x));
    return t.length ? t.join(" ") : s;
  }
  function lev(a, b) {
    if (a === b) return 0;
    const m = a.length, n = b.length;
    if (!m) return n; if (!n) return m;
    let prev = new Array(n + 1), cur = new Array(n + 1);
    for (let j = 0; j <= n; j++) prev[j] = j;
    for (let i = 1; i <= m; i++) {
      cur[0] = i;
      for (let j = 1; j <= n; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1,
                          prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      [prev, cur] = [cur, prev];
    }
    return prev[n];
  }
  function ratio(a, b) {
    if (!a.length && !b.length) return 100;
    const d = lev(a, b);
    return (1 - d / Math.max(a.length, b.length)) * 100;
  }
  function tokenSortRatio(a, b) {
    const sa = a.split(" ").sort().join(" ");
    const sb = b.split(" ").sort().join(" ");
    return ratio(sa, sb);
  }
  function tokenSetRatio(a, b) {
    const A = new Set(a.split(" ")), B = new Set(b.split(" "));
    const inter = [...A].filter(x => B.has(x)).sort();
    if (!inter.length) return 0;
    const dA = [...A].filter(x => !B.has(x)).sort();
    const dB = [...B].filter(x => !A.has(x)).sort();
    if (!dA.length || !dB.length) return 100;
    const t0 = inter.join(" ");
    const t1 = t0 + " " + dA.join(" ");
    const t2 = t0 + " " + dB.join(" ");
    return Math.max(ratio(t0, t1), ratio(t0, t2), ratio(t1, t2));
  }

  function prepSanctions(records) {
    return records.map(r => ({
      rec: r,
      cands: [r.name, ...(r.aliases || [])].map(c => {
        const raw = normalize(c), core = stripSuffix(raw);
        return { text: c, raw, core, toks: new Set(core.split(" ")) };
      })
    }));
  }

  function matchSanctions(prepped, name, quickReject) {
    const tRaw = normalize(name), tCore = stripSuffix(tRaw);
    const tToks = new Set(tCore.split(" "));
    let best = { score: 0, direct: false, ev: null };
    for (const p of prepped) {
      for (const c of p.cands) {
        if (quickReject) {
          let shared = false;
          for (const tk of c.toks) if (tk.length >= 3 && tToks.has(tk)) { shared = true; break; }
          if (!shared) continue;
        }
        let score = 0, direct = false, kind = "";
        if (tRaw === c.raw) { score = 1.0; direct = true; kind = "exact"; }
        else {
          const srt = tokenSortRatio(tCore, c.core);
          if (srt >= 90) { score = 0.9 * (srt / 100); kind = "fuzzy " + srt.toFixed(0) + "%"; }
          else {
            const st = tokenSetRatio(tCore, c.core);
            const meaningful = c.core.split(" ").length >= 2 || c.core.length >= 6;
            if (st >= 95 && meaningful) { score = 0.85; kind = "affiliate-containment"; }
          }
        }
        if (score > best.score) {
          best = { score, direct, ev: { matched: c.text, kind,
            list: p.rec.list, program: p.rec.program, year: p.rec.year,
            note: p.rec.note } };
        }
      }
      if (best.score === 1.0) break;
    }
    return best;
  }

  function geoRisk(juris, ownerJuris) {
    const all = [juris, ownerJuris].filter(Boolean).map(x => x.toUpperCase());
    const hiHits = all.filter(j => HIGH_J.has(j));
    if (hiHits.length) return { score: 0.9, hits: hiHits,
      cat: "FATF call-for-action / comprehensively sanctioned jurisdiction" };
    const gHits = all.filter(j => GREY_J.has(j));
    if (gHits.length) return { score: 0.5, hits: gHits,
      cat: "FATF increased-monitoring (grey list) jurisdiction" };
    return { score: 0.0, hits: [], cat: "No listed-jurisdiction exposure" };
  }

  function opacity(registryId, founded, nowYear) {
    let s = registryId ? 0 : 0.5;
    let isNew = false;
    if (founded && (nowYear - founded) <= 1) { s += 0.4; isNew = true; }
    return { score: Math.min(s, 1), registryId: !!registryId, isNew };
  }

  function industry(naics, juris, ownerJuris) {
    if (!naics) return { score: 0, rule: null };
    const hi = HIGH_J.has((juris || "").toUpperCase()) ||
               HIGH_J.has((ownerJuris || "").toUpperCase());
    const grey = GREY_J.has((juris || "").toUpperCase()) ||
                 GREY_J.has((ownerJuris || "").toUpperCase());
    if (DUAL_USE.some(p => naics.startsWith(p))) {
      if (hi) return { score: 0.7, rule: "Dual-use goods category combined with sanctioned-jurisdiction exposure" };
      if (grey) return { score: 0.5, rule: "Dual-use goods category combined with grey-list-jurisdiction exposure" };
    }
    if (DIVERSION_LOGISTICS.some(p => naics.startsWith(p)) && hi)
      return { score: 0.6, rule: "Diversion-prone logistics category with sanctioned-jurisdiction exposure" };
    return { score: 0, rule: null };
  }

  function financial(cik) {
    if (!cik) return { score: null, coverage: false };
    const c = FIN_CACHE[cik];
    if (!c) return { score: null, coverage: false, cik };
    let s;
    if (c.ratio >= 0.15) s = 0.0; else if (c.ratio >= 0) s = 0.3; else s = 0.8;
    return { score: s, coverage: true, ratio: c.ratio, fy: c.fy, cik };
  }

  const TIERS = [[0.6, "CRITICAL"], [0.4, "HIGH"], [0.2, "MEDIUM"], [0, "LOW"]];

  function screen(prepped, entity, opts) {
    opts = opts || {};
    const nowYear = opts.nowYear || 2026;
    const m = matchSanctions(prepped, entity.name, !!opts.quickReject);
    const g = geoRisk(entity.jurisdiction, entity.ownerJurisdiction);
    const o = opacity(entity.registryId, entity.founded, nowYear);
    const i = industry(entity.naics, entity.jurisdiction, entity.ownerJurisdiction);
    const f = financial(entity.cik);

    const sig = {
      sanctions: { score: m.score, detail: m },
      financial: { score: f.score, detail: f },
      geographic: { score: g.score, detail: g },
      opacity: { score: o.score, detail: o },
      industry: { score: i.score, detail: i },
    };
    let num = 0, den = 0;
    for (const k in sig) {
      if (sig[k].score === null) continue;
      num += sig[k].score * WEIGHTS[k];
      den += WEIGHTS[k];
    }
    const composite = den ? num / den : 0;
    let tier = TIERS.find(t => composite >= t[0])[1];
    if (m.direct) tier = "CRITICAL";
    return { name: entity.name, tier, composite: Math.round(composite * 1000) / 1000,
             override: m.direct, signals: sig };
  }

  g.VET_ENGINE = { normalize, stripSuffix, tokenSortRatio, tokenSetRatio,
                   prepSanctions, matchSanctions, geoRisk, opacity, industry,
                   financial, screen, WEIGHTS, HIGH_J, GREY_J };
})(typeof globalThis !== "undefined" ? globalThis : window);
