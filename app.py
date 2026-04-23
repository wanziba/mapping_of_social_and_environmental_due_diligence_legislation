import re
import json
import os
from pathlib import Path
from typing import List, Tuple
from urllib import request, error

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from ui.fragments import FOOTER_NOTICE_HTML, HERO_HTML


st.set_page_config(
    page_title="尽职调查立法导航工具",
    page_icon="📘",
    layout="wide",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


EU_MEMBERS = {
    "Austria",
    "Belgium",
    "Bulgaria",
    "Croatia",
    "Cyprus",
    "Czech Republic",
    "Denmark",
    "Estonia",
    "Finland",
    "France",
    "Germany",
    "Greece",
    "Hungary",
    "Ireland",
    "Italy",
    "Latvia",
    "Lithuania",
    "Luxembourg",
    "Malta",
    "Netherlands",
    "Poland",
    "Portugal",
    "Romania",
    "Slovakia",
    "Slovenia",
    "Spain",
    "Sweden",
}

COUNTRY_POINTS = {
    "UK": (54.0, -2.5),
    "Australia": (-25.0, 134.0),
    "Canada": (56.0, -106.0),
    "EU": (50.85, 4.35),
    "US": (39.8, -98.6),
    "France": (46.2, 2.2),
    "Norway": (60.5, 8.5),
    "Germany": (51.0, 10.0),
    "Switzerland": (46.8, 8.2),
    "South Korea": (36.5, 127.8),
    "UAE": (24.0, 54.0),
}

COUNTRY_ZH = {
    "UK": "英国",
    "Australia": "澳大利亚",
    "Canada": "加拿大",
    "EU": "欧盟",
    "US": "美国",
    "France": "法国",
    "Norway": "挪威",
    "Germany": "德国",
    "Switzerland": "瑞士",
    "South Korea": "韩国",
    "UAE": "阿联酋",
}

STEP_LABELS = {
    1: "第1步：将负责任商业行为融入政策和管理体系",
    2: "第2步：识别与评估影响",
    3: "第3步：终止、预防与减缓影响",
    4: "第4步：跟踪实施与结果",
    5: "第5步：沟通影响处理方式",
    6: "第6步：提供或合作进行补救",
}


@st.cache_data
def load_data() -> Tuple[pd.DataFrame, pd.DataFrame]:
    laws = pd.read_csv(DATA_DIR / "legislations.csv")
    steps = pd.read_csv(DATA_DIR / "six_steps.csv")

    laws = laws.fillna("")
    steps = steps.fillna("")

    laws["search_blob"] = (
        laws["name_en"].astype(str)
        + " "
        + laws["name_cn"].astype(str)
        + " "
        + laws["country"].astype(str)
        + " "
        + laws["category"].astype(str)
        + " "
        + laws["entity_scope"].astype(str)
        + " "
        + laws["supply_chain_scope"].astype(str)
        + " "
        + laws["issue_scope"].astype(str)
        + " "
        + laws["enforcement_authority"].astype(str)
    ).str.lower()
    laws["country_zh"] = laws["country"].map(lambda c: COUNTRY_ZH.get(str(c), str(c)))

    return laws, steps


def inject_theme() -> None:
    css = (BASE_DIR / "assets" / "styles.css").read_text(encoding="utf-8")
    st.markdown(
        f"<style>{css}</style>",
        unsafe_allow_html=True,
    )


def tokenize_query(text: str) -> List[str]:
    text = (text or "").strip().lower()
    if not text:
        return []

    zh_tokens = re.findall(r"[\u4e00-\u9fff]+", text)
    en_tokens = re.findall(r"[a-z0-9_\-\.]+", text)
    merged = zh_tokens + en_tokens
    return [tok for tok in merged if len(tok) >= 1]


def input_signal_score(search_blob: str, industry: str, product: str) -> int:
    score = 0
    industry_tokens = tokenize_query(industry)
    product_tokens = tokenize_query(product)

    for tok in industry_tokens:
        if tok in search_blob:
            score += 2

    for tok in product_tokens:
        if tok in search_blob:
            score += 2

    if industry and industry.lower() in search_blob:
        score += 2
    if product and product.lower() in search_blob:
        score += 2

    if any(k in (industry + " " + product).lower() for k in ["ai", "人工智能", "算法"]):
        if ("ai" in search_blob) or ("人工智能" in search_blob):
            score += 3

    if any(k in (industry + " " + product).lower() for k in ["矿", "gold", "battery", "冲突矿产", "电池", "黄金"]):
        if any(k in search_blob for k in ["矿", "gold", "battery", "冲突矿产", "电池", "黄金"]):
            score += 2

    if any(k in (industry + " " + product).lower() for k in ["森林", "木材", "咖啡", "可可", "棕榈", "deforestation"]):
        if any(k in search_blob for k in ["森林", "木材", "咖啡", "可可", "棕榈", "deforestation"]):
            score += 2

    return score


def country_filter(laws: pd.DataFrame, operating_country: str) -> pd.DataFrame:
    if operating_country == "全部":
        return laws.copy()

    mask = laws["country"].eq(operating_country)
    if operating_country in EU_MEMBERS:
        mask = mask | laws["country"].eq("EU")

    return laws.loc[mask].copy()


def ensure_eu_member_coverage(
    base: pd.DataFrame, result: pd.DataFrame, operating_country: str
) -> pd.DataFrame:
    if operating_country not in EU_MEMBERS:
        return result

    mandatory = base.loc[base["country"].isin([operating_country, "EU"])].copy()
    if mandatory.empty:
        return result

    if result.empty:
        return mandatory.drop_duplicates(subset=["id"])

    merged = pd.concat([result, mandatory], ignore_index=True)
    return merged.drop_duplicates(subset=["id"], keep="first")


def get_key_requirements(steps_df: pd.DataFrame, legislation_id: str) -> pd.DataFrame:
    if "legislation_id" not in steps_df.columns:
        return pd.DataFrame(columns=["步骤", "关键要求"])

    records: list[dict[str, object]] = []
    step_columns = [f"step{i}" for i in range(1, 7)]

    # Preferred schema: one row per legislation with step1-step6 columns.
    if set(step_columns).issubset(set(steps_df.columns)):
        law_rows = steps_df.loc[
            steps_df["legislation_id"].astype(str) == str(legislation_id),
            ["legislation_id", *step_columns],
        ].copy()
        if law_rows.empty:
            return pd.DataFrame(columns=["步骤", "关键要求"])

        row = law_rows.iloc[0]
        for step_num, column in enumerate(step_columns, start=1):
            value = str(row.get(column, "")).strip()
            if not value or value.lower() == "nan":
                continue
            records.append({"step": step_num, "requirement_short": value})

    # Backward-compatible schema: multiple rows with step + requirement_short.
    elif {"step", "requirement_short"}.issubset(set(steps_df.columns)):
        legacy_rows = steps_df.loc[
            steps_df["legislation_id"].astype(str) == str(legislation_id),
            ["step", "requirement_short"],
        ].copy()
        if legacy_rows.empty:
            return pd.DataFrame(columns=["步骤", "关键要求"])

        legacy_rows["step"] = pd.to_numeric(legacy_rows["step"], errors="coerce")
        legacy_rows = legacy_rows.dropna(subset=["step"])
        legacy_rows = legacy_rows.sort_values("step")
        for _, row in legacy_rows.iterrows():
            value = str(row.get("requirement_short", "")).strip()
            if not value or value.lower() == "nan":
                continue
            records.append({"step": int(row["step"]), "requirement_short": value})

    if not records:
        return pd.DataFrame(columns=["步骤", "关键要求"])

    req = pd.DataFrame(records)
    raw_steps = req["step"].astype(int).unique().tolist()
    if len(raw_steps) == 1 and raw_steps[0] == 1:
        req["step"] = ""
    else:
        req["step"] = req["step"].map(lambda x: STEP_LABELS.get(int(x), f"第{x}步"))
    req.columns = ["步骤", "关键要求"]
    return req


def _split_requirement_lines(text: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"[；;]", str(text)) if p and str(p).strip()]
    return [f"- {part}" for part in parts]


def _format_requirement_rows(req: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for _, row in req.iterrows():
        step_label = str(row["步骤"]).strip()
        lines = _split_requirement_lines(str(row["关键要求"]))
        if not lines:
            lines = ["- 未明确说明"]
        for idx, line in enumerate(lines):
            rows.append(
                {
                    "步骤": step_label if idx == 0 else "",
                    "关键要求": line,
                }
            )
    return pd.DataFrame(rows, columns=["步骤", "关键要求"])


def _render_requirements_table(req_rows: pd.DataFrame) -> None:
    table_rows: list[str] = []
    for _, row in req_rows.iterrows():
        step = str(row["步骤"]).strip()
        requirement = str(row["关键要求"]).strip()
        table_rows.append(
            "<tr>"
            f"<td>{step}</td>"
            f"<td>{requirement}</td>"
            "</tr>"
        )

    html = (
        '<div class="requirements-table-wrap">'
        '<table class="requirements-table">'
        '<thead><tr><th>步骤</th><th>关键要求</th></tr></thead>'
        f"<tbody>{''.join(table_rows)}</tbody>"
        "</table>"
        "</div>"
    )
    st.markdown(html, unsafe_allow_html=True)


def _llm_rank_legislations(
    laws: pd.DataFrame,
    operating_country: str,
    industry: str,
    product: str,
) -> tuple[list[str], str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return [], "未配置", "未检测到 DEEPSEEK_API_KEY"

    candidates_full = laws[["id", "name_cn", "name_en", "country_zh", "category", "issue_scope"]].to_dict(
        orient="records"
    )
    candidates_min = laws[["id", "country_zh", "category"]].to_dict(orient="records")

    prompt = {
        "operating_country": COUNTRY_ZH.get(operating_country, operating_country),
        "industry": industry,
        "product": product,
        "task": "从候选立法中选出所有相关立法，按相关性降序返回id数组。",
        "rules": ["只返回JSON数组", "数组元素必须是候选id", "按相关性降序"],
        "candidates": candidates_full,
    }

    def parse_id_array(content: str) -> list[str] | None:
        text = (content or "").strip()
        if not text:
            return None

        try:
            obj = json.loads(text)
            if isinstance(obj, list):
                return [str(x) for x in obj]
        except Exception:
            pass

        fenced = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, flags=re.S)
        if fenced:
            try:
                obj = json.loads(fenced.group(1))
                if isinstance(obj, list):
                    return [str(x) for x in obj]
            except Exception:
                pass

        bracket = re.search(r"\[[\s\S]*\]", text)
        if bracket:
            try:
                obj = json.loads(bracket.group(0))
                if isinstance(obj, list):
                    return [str(x) for x in obj]
            except Exception:
                pass

        return None

    def call_deepseek(prompt_obj: dict) -> tuple[list[str], str]:
        payload = {
            "model": "deepseek-chat",
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "你是合规匹配助手，只输出JSON数组。"},
                {"role": "user", "content": json.dumps(prompt_obj, ensure_ascii=False)},
            ],
        }

        req = request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        with request.urlopen(req, timeout=25) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
        content = resp_json["choices"][0]["message"]["content"]
        ids = parse_id_array(content)
        if not ids:
            return [], "模型返回格式无法解析为ID数组"

        valid_ids = set(laws["id"].astype(str).tolist())
        picked = [str(i) for i in ids if str(i) in valid_ids]
        if not picked:
            return [], "模型返回ID不在候选立法中"
        return picked, ""

    try:
        picked, reason = call_deepseek(prompt)
        if not picked:
            return [], "调用失败", reason
        return picked, "大模型(DeepSeek)", ""
    except error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        if e.code == 400 and "Content Exists Risk" in body:
            try:
                prompt_min = dict(prompt)
                prompt_min["candidates"] = candidates_min
                picked, reason = call_deepseek(prompt_min)
                if not picked:
                    return [], "调用失败", reason
                return picked, "大模型(DeepSeek)", ""
            except Exception as retry_e:
                return [], "调用失败", f"{type(retry_e).__name__}: {retry_e}"
        return [], "调用失败", f"HTTPError {e.code}: {body[:200]}"
    except Exception as e:
        return [], "调用失败", f"{type(e).__name__}: {e}"


def ensure_llm_configured() -> None:
    if os.getenv("DEEPSEEK_API_KEY", "").strip():
        return

    st.error(
        "未检测到大模型配置。请先配置环境变量 DEEPSEEK_API_KEY，然后刷新页面继续使用。"
    )
    st.info("示例：在虚拟环境激活后执行 `export DEEPSEEK_API_KEY=你的Key`。")
    st.stop()


def render_hero() -> None:
    st.markdown(HERO_HTML, unsafe_allow_html=True)


def render_metrics(filtered_laws: pd.DataFrame) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">适用法律</div>
                <div class="metric-value">{filtered_laws['id'].nunique()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">司法管辖区</div>
                <div class="metric-value">{filtered_laws['country'].nunique()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"""
            <div class="metric-box">
                <div class="metric-label">执法机构</div>
                <div class="metric-value">{filtered_laws['enforcement_authority'].nunique()}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_compliance_query(laws: pd.DataFrame) -> pd.DataFrame:
    st.markdown('<div class="panel-dark">', unsafe_allow_html=True)

    countries = ["全部"] + sorted(laws["country"].dropna().unique().tolist())

    with st.form("query_form"):
        col1, col2, col3 = st.columns([1.1, 1.2, 1.2])
        with col1:
            operating_country = st.selectbox(
                "运营国家/地区",
                countries,
                index=0,
                format_func=lambda c: "全部" if c == "全部" else COUNTRY_ZH.get(c, c),
            )
        with col2:
            industry = st.text_input("行业", placeholder="例如：汽车、电池、数字平台、矿产、服装")
        with col3:
            product = st.text_input("产品类型", placeholder="例如：AI系统、黄金、咖啡、电子产品")
        submitted = st.form_submit_button("查询")

    st.markdown('</div>', unsafe_allow_html=True)

    if "filtered_laws" not in st.session_state:
        st.session_state["filtered_laws"] = laws.copy()
        st.session_state["match_source"] = "规则匹配"
    if "query_version" not in st.session_state:
        st.session_state["query_version"] = 0
    if "active_country" not in st.session_state:
        st.session_state["active_country"] = None
    if "selected_legislation_id" not in st.session_state:
        st.session_state["selected_legislation_id"] = None

    if submitted:
        base = country_filter(laws, operating_country)
        llm_ids, match_source, fail_reason = _llm_rank_legislations(
            base, operating_country, industry, product
        )

        if llm_ids:
            result = base.loc[base["id"].astype(str).isin(llm_ids)].copy()
            order = {law_id: idx for idx, law_id in enumerate(llm_ids)}
            result["_order"] = result["id"].astype(str).map(lambda x: order.get(str(x), 999))
            result = result.sort_values("_order").drop(columns=["_order"])
        else:
            st.warning(
                "大模型调用失败，本次未返回匹配结果。"
                f"原因：{fail_reason or '未知错误'}。请检查 API Key 或网络后重试。"
            )
            st.session_state["match_source"] = match_source
            return st.session_state["filtered_laws"]

        result = ensure_eu_member_coverage(base, result, operating_country)

        st.session_state["filtered_laws"] = result
        st.session_state["match_source"] = match_source
        st.session_state["query_version"] = int(st.session_state.get("query_version", 0)) + 1
        st.session_state["active_country"] = None
        st.session_state["selected_legislation_id"] = None

    result = st.session_state["filtered_laws"]
    render_metrics(result)
    st.caption("查询结果将直接在下方地图中显示。")
    return result


def _wrap_text(text: str, width: int = 18) -> str:
    chars = list(str(text))
    return "<br>".join("".join(chars[i : i + width]) for i in range(0, len(chars), width))


def build_map_frame(laws: pd.DataFrame) -> pd.DataFrame:
    grouped = (
        laws.groupby("country", as_index=False)
        .agg(
            law_count=("id", "nunique"),
            laws_cn=("name_cn", lambda x: "；".join(sorted(set(x)))),
        )
        .copy()
    )

    def point_lat(country_value: object) -> float | None:
        country = str(country_value) if country_value is not None else ""
        return COUNTRY_POINTS.get(country, (None, None))[0]

    def point_lon(country_value: object) -> float | None:
        country = str(country_value) if country_value is not None else ""
        return COUNTRY_POINTS.get(country, (None, None))[1]

    grouped["lat"] = grouped["country"].map(point_lat)
    grouped["lon"] = grouped["country"].map(point_lon)
    grouped["country_zh"] = grouped["country"].map(lambda c: COUNTRY_ZH.get(str(c), str(c)))
    grouped["laws_cn_wrapped"] = grouped["laws_cn"].map(lambda x: _wrap_text(str(x), 18))

    grouped = grouped.dropna(subset=["lat", "lon"])
    return grouped


def compute_map_view(geo_df: pd.DataFrame) -> tuple[dict[str, float], float]:
    if geo_df.empty:
        return {"lat": 20.0, "lon": 0.0}, 0.8

    lon_min = float(geo_df["lon"].min())
    lon_max = float(geo_df["lon"].max())
    lat_min = float(geo_df["lat"].min())
    lat_max = float(geo_df["lat"].max())

    lon_span = max(lon_max - lon_min, 8.0)
    lat_span = max(lat_max - lat_min, 6.0)
    max_span = max(lon_span / 360.0, lat_span / 170.0)

    if max_span > 0.65:
        zoom = 0.8
    elif max_span > 0.45:
        zoom = 1.1
    elif max_span > 0.28:
        zoom = 1.6
    elif max_span > 0.16:
        zoom = 2.1
    elif max_span > 0.09:
        zoom = 2.7
    elif max_span > 0.05:
        zoom = 3.4
    else:
        zoom = 4.2

    center = {
        "lat": (lat_min + lat_max) / 2,
        "lon": (lon_min + lon_max) / 2,
    }
    return center, zoom


def render_map(laws: pd.DataFrame) -> None:
    if laws.empty:
        st.warning("当前查询条件没有匹配到立法，请调整筛选条件后重试。")
        return

    active_country = st.session_state.get("active_country")
    valid_countries = set(laws["country"].astype(str).tolist())
    if active_country and str(active_country) not in valid_countries:
        active_country = None
        st.session_state["active_country"] = None

    geo_df = build_map_frame(laws)
    highlight_df = geo_df.loc[geo_df["country"].astype(str) == str(active_country)].copy()
    map_center, map_zoom = compute_map_view(geo_df)

    fig = go.Figure(
        data=go.Scattermapbox(
            lon=geo_df["lon"],
            lat=geo_df["lat"],
            customdata=geo_df[["country", "country_zh", "law_count", "laws_cn_wrapped"]].values,
            mode="markers",
            marker=dict(
                size=geo_df["law_count"] * 4 + 10,
                color="#1c69d4",
                opacity=0.88,
            ),
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>"
                "立法数量: %{customdata[2]}<br>"
                "已纳入立法:<br>%{customdata[3]}<extra></extra>"
            ),
            hoverlabel=dict(font=dict(size=16), align="left"),
        )
    )

    if not highlight_df.empty:
        fig.add_trace(
            go.Scattermapbox(
                lon=highlight_df["lon"],
                lat=highlight_df["lat"],
                mode="markers",
                marker=dict(
                    size=highlight_df["law_count"] * 4 + 22,
                    color="rgba(246,194,68,0.45)",
                    opacity=0.9,
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.update_layout(
        height=530,
        margin=dict(l=0, r=0, t=8, b=0),
        paper_bgcolor="white",
        plot_bgcolor="white",
        mapbox=dict(
            style="carto-positron",
            center=map_center,
            zoom=map_zoom,
        ),
    )

    st.caption("点击地图点位可切换辖区，查看立法细节。")
    event = st.plotly_chart(
        fig,
        use_container_width=True,
        key=f"law_geo_map_{int(st.session_state.get('query_version', 0))}",
        on_select="rerun",
        selection_mode="points",
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "displaylogo": False,
        },
    )

    selected_country = None
    if event and isinstance(event, dict):
        points = event.get("selection", {}).get("points", [])
        if points:
            selected_country = points[0].get("customdata", [None])[0]

    if selected_country and str(selected_country) in valid_countries:
        if str(selected_country) != str(st.session_state.get("active_country")):
            st.session_state["selected_legislation_id"] = None
        st.session_state["active_country"] = str(selected_country)


def render_detail_and_requirements(laws: pd.DataFrame, steps: pd.DataFrame) -> None:
    if laws.empty:
        st.warning("暂无立法数据。")
        return

    valid_countries = set(laws["country"].astype(str).tolist())
    active_country = st.session_state.get("active_country")
    if active_country and str(active_country) in valid_countries:
        subset = laws.loc[laws["country"].astype(str) == str(active_country)].copy()
    else:
        subset = laws.copy()
        active_country = None
        st.session_state["active_country"] = None

    subset = subset.reset_index(drop=True)

    detail_cols = [
        "country_zh",
        "name_cn",
        "name_en",
        "entity_scope",
        "supply_chain_scope",
        "issue_scope",
        "enforcement_authority",
    ]

    details = subset[detail_cols].rename(
        columns={
            "country_zh": "国家/地区",
            "name_cn": "立法名称（中文）",
            "name_en": "Legislation",
            "entity_scope": "适用主体",
            "supply_chain_scope": "供应链深度",
            "issue_scope": "议题范围",
            "enforcement_authority": "执法机构",
        }
    )

    st.markdown("#### 立法详情")
    st.caption(f"当前显示 {len(subset)} 项立法。")
    detail_event = st.dataframe(
        details,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
        key=f"law_detail_table_{active_country or 'all'}_{int(st.session_state.get('query_version', 0))}",
    )

    def _extract_selected_row(event: object) -> int | None:
        if event is None:
            return None

        selection: object | None = None
        if isinstance(event, dict):
            selection = event.get("selection", {})
        else:
            selection = getattr(event, "selection", None)

        if selection is None:
            return None

        rows: object | None = None
        if isinstance(selection, dict):
            rows = selection.get("rows", [])
        else:
            rows = getattr(selection, "rows", None)

        if not rows or not isinstance(rows, (list, tuple)):
            return None

        first = rows[0]
        if isinstance(first, dict):
            first = first.get("index", first.get("row", first.get("id")))
        if first is None:
            return None

        try:
            return int(first)
        except (TypeError, ValueError):
            return None

    selected_legislation_id = st.session_state.get("selected_legislation_id")
    visible_law_ids = set(subset["id"].astype(str).tolist())
    if selected_legislation_id and str(selected_legislation_id) not in visible_law_ids:
        selected_legislation_id = None
        st.session_state["selected_legislation_id"] = None

    selected_row_index = _extract_selected_row(detail_event)
    if selected_row_index is not None and 0 <= selected_row_index < len(subset):
        selected_legislation_id = str(subset.iloc[selected_row_index]["id"])
        st.session_state["selected_legislation_id"] = selected_legislation_id

    st.markdown("#### 关键要求")

    if not selected_legislation_id:
        st.info("请先在上方“立法详情”中选择一条立法后查看关键要求。")
        return

    try:
        req = get_key_requirements(steps, str(selected_legislation_id))
        if req.empty:
            st.info("该立法在六步表中暂无结构化条目。")
        else:
            req_rows = _format_requirement_rows(req)
            _render_requirements_table(req_rows)
    except Exception:
        st.error("关键要求加载失败，请重新选择立法后再试。")


def render_sidebar() -> None:
    st.sidebar.markdown("## 使用说明")
    st.sidebar.write("1) 在合规查询区输入运营国家/行业/产品类型")
    st.sidebar.write("2) 查看适用立法和关键要求")
    st.sidebar.write("3) 在地图中点击法域查看该辖区详情")

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 数据来源")
    st.sidebar.write("- data/legislations.csv")
    st.sidebar.write("- data/six_steps.csv")


def render_footer_notice() -> None:
    st.markdown("---")
    st.markdown(FOOTER_NOTICE_HTML, unsafe_allow_html=True)


def main() -> None:
    inject_theme()
    ensure_llm_configured()
    laws, steps = load_data()

    render_hero()

    left_col, right_col = st.columns([1.0, 1.45], gap="large")
    with left_col:
        filtered_laws = render_compliance_query(laws)
    with right_col:
        render_map(filtered_laws)

    render_detail_and_requirements(filtered_laws, steps)

    render_footer_notice()


if __name__ == "__main__":
    main()
