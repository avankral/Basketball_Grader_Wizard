"""Recommendations panel component.

Displays grade recommendations with:
- Filterable table
- Expandable evidence
- Accept/Override actions
- Bulk operations
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from src.grading.overrides import OverrideManager
from src.models.recommendation import Override, Recommendation, RecommendationType


def _get_rec_type_str(rec_type: RecommendationType | str) -> str:
    """Normalize recommendation type to string for comparison."""
    return rec_type.value if hasattr(rec_type, "value") else str(rec_type)


def render_recommendations_panel(
    recommendations: list[Recommendation],
    override_manager: OverrideManager | None = None,
    season: str = "Autumn 2026",
) -> None:
    """Render the recommendations panel.

    Args:
        recommendations: List of all recommendations.
        override_manager: Manager for recording overrides.
        season: Current season identifier.
    """
    if not recommendations:
        st.info("No recommendations available. Upload data to generate recommendations.")
        return

    st.subheader("📋 Grade Recommendations")

    # Filter tabs
    tab_all, tab_pending, tab_review = st.tabs(
        [
            f"All ({len(recommendations)})",
            f"Pending ({_count_pending(recommendations)})",
            f"Review Needed ({_count_review(recommendations)})",
        ]
    )

    with tab_all:
        _render_recommendations_table(recommendations, override_manager, season, filter_type=None)

    with tab_pending:
        pending = [
            r
            for r in recommendations
            if _get_rec_type_str(r.recommendation_type) in ("promote", "demote")
        ]
        _render_recommendations_table(pending, override_manager, season, filter_type="pending")

    with tab_review:
        review = [
            r for r in recommendations if _get_rec_type_str(r.recommendation_type) == "review_needed"
        ]
        _render_recommendations_table(review, override_manager, season, filter_type="review")


def _count_pending(recommendations: list[Recommendation]) -> int:
    """Count pending recommendations."""
    return sum(
        1
        for r in recommendations
        if _get_rec_type_str(r.recommendation_type) in ("promote", "demote")
    )


def _count_review(recommendations: list[Recommendation]) -> int:
    """Count review needed recommendations."""
    return sum(
        1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "review_needed"
    )


def _render_recommendations_table(
    recommendations: list[Recommendation],
    override_manager: OverrideManager | None,
    season: str,
    filter_type: str | None,
) -> None:
    """Render recommendations as interactive table.

    Args:
        recommendations: Filtered recommendations.
        override_manager: Override manager.
        season: Current season.
        filter_type: Type of filter applied.
    """
    if not recommendations:
        st.info("No recommendations in this category.")
        return

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        promote = sum(
            1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "promote"
        )
        st.metric("🟢 Promote", promote)
    with col2:
        demote = sum(
            1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "demote"
        )
        st.metric("🔴 Demote", demote)
    with col3:
        monitor = sum(
            1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "monitor"
        )
        st.metric("👀 Monitor", monitor)
    with col4:
        review = sum(
            1 for r in recommendations if _get_rec_type_str(r.recommendation_type) == "review_needed"
        )
        st.metric("⚠️ Review", review)

    # Sort options
    sort_by = st.selectbox(
        "Sort by",
        options=["Confidence (High first)", "Team Name", "Current Grade"],
        key=f"sort_{filter_type}",
    )

    # Sort recommendations
    if sort_by == "Confidence (High first)":
        conf_order = {"high": 0, "medium": 1, "low": 2}
        recommendations = sorted(
            recommendations, key=lambda r: conf_order.get(r.confidence.value if hasattr(r.confidence, "value") else str(r.confidence), 99)
        )
    elif sort_by == "Team Name":
        recommendations = sorted(recommendations, key=lambda r: r.team_name)
    else:
        recommendations = sorted(recommendations, key=lambda r: r.current_grade or "ZZZ")

    # Render each recommendation as expandable card
    for rec in recommendations:
        _render_recommendation_card(rec, override_manager, season, filter_type)

    # Bulk actions
    if filter_type == "pending" and recommendations:
        st.divider()
        col1, col2 = st.columns(2)

        with col1:
            if st.button("✅ Accept All High-Confidence", key="accept_all_high"):
                def get_conf(r: Recommendation) -> str:
                    return r.confidence.value if hasattr(r.confidence, "value") else str(r.confidence)
                high_conf = [r for r in recommendations if get_conf(r) == "high"]
                st.success(f"Accepted {len(high_conf)} high-confidence recommendations.")

        with col2:
            if st.button("📥 Export Pending", key="export_pending"):
                _export_recommendations(recommendations)


def _render_recommendation_card(
    rec: Recommendation,
    override_manager: OverrideManager | None,
    season: str,
    filter_type: str | None = None,
) -> None:
    """Render a single recommendation as an expandable card.

    Args:
        rec: Recommendation to display.
        override_manager: Override manager.
        season: Current season.
        filter_type: Tab filter type for unique keys.
    """
    # Determine icon and color
    icons = {
        "promote": "🟢",
        "demote": "🔴",
        "monitor": "👀",
        "review_needed": "⚠️",
        "no_change": "✅",
    }
    rec_type_str = _get_rec_type_str(rec.recommendation_type)
    icon = icons.get(rec_type_str, "")

    # Confidence badge
    conf_colors = {"high": "🟢", "medium": "🟡", "low": "🔴"}
    conf_val = rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence)
    rec_type = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
    conf_badge = conf_colors.get(conf_val, "")

    # Create header
    grade_change = ""
    if rec.current_grade and rec.recommended_grade:
        grade_change = f" ({rec.current_grade} → {rec.recommended_grade})"

    header = f"{icon} **{rec.team_name}** — {rec_type.upper()}{grade_change} {conf_badge}"

    with st.expander(header, expanded=rec.requires_action):
        # Basic info
        col1, col2, col3 = st.columns(3)
        with col1:
            st.write(f"**Current Grade:** {rec.current_grade or 'N/A'}")
        with col2:
            st.write(f"**Recommended:** {rec.recommended_grade or 'No change'}")
        with col3:
            st.write(f"**Confidence:** {conf_val.title()}")

        # Explanation
        st.info(rec.explanation)

        # Evidence
        if rec.evidence:
            st.markdown("**Evidence:**")
            for e in rec.evidence:
                st.write(f"- {e}")

        # Concerns
        if rec.concerns:
            st.markdown("**Concerns:**")
            for c in rec.concerns:
                st.warning(c)

        # SoS note
        if rec.strength_of_schedule_note:
            st.markdown("**Strength of Schedule:**")
            st.caption(rec.strength_of_schedule_note)

        # Transitive variance
        if rec.transitive_variance_note:
            st.markdown("**Transitive Variance:**")
            st.code(rec.transitive_variance_note)

        # Actions
        if rec.requires_action and override_manager:
            st.divider()
            col1, col2, col3 = st.columns(3)

            with col1:
                key_suffix = f"{filter_type}_{rec.team_name}" if filter_type else rec.team_name
                if st.button("✅ Accept", key=f"accept_{key_suffix}"):
                    override = Override(
                        team_name=rec.team_name,
                        sheet_name=rec.sheet_name,
                        original_recommendation=rec.recommendation_type,
                        original_grade=rec.current_grade,
                        admin_decision="accept",
                        final_grade=rec.recommended_grade,
                        reason="Accepted system recommendation",
                        season=season,
                    )
                    override_manager.record_override(override)
                    st.success("Recommendation accepted!")
                    st.rerun()

            with col2:
                if st.button("❌ Reject", key=f"reject_{key_suffix}"):
                    st.session_state[f"show_reject_{key_suffix}"] = True

            with col3:
                if st.button("📝 Override", key=f"override_{key_suffix}"):
                    st.session_state[f"show_override_{key_suffix}"] = True

            # Reject modal
            if st.session_state.get(f"show_reject_{key_suffix}"):
                reason = st.text_input(
                    "Reason for rejection:", key=f"reject_reason_{key_suffix}"
                )
                if st.button("Confirm Rejection", key=f"confirm_reject_{key_suffix}"):
                    if reason:
                        override = Override(
                            team_name=rec.team_name,
                            sheet_name=rec.sheet_name,
                            original_recommendation=rec.recommendation_type,
                            original_grade=rec.current_grade,
                            admin_decision="reject",
                            final_grade=rec.current_grade,
                            reason=reason,
                            season=season,
                        )
                        override_manager.record_override(override)
                        st.success("Recommendation rejected.")
                        st.session_state[f"show_reject_{key_suffix}"] = False
                        st.rerun()
                    else:
                        st.error("Please provide a reason.")

            # Override modal
            if st.session_state.get(f"show_override_{key_suffix}"):
                new_grade = st.text_input("New grade:", key=f"new_grade_{key_suffix}")
                reason = st.text_input("Override reason:", key=f"override_reason_{key_suffix}")
                if st.button("Confirm Override", key=f"confirm_override_{key_suffix}"):
                    if new_grade and reason:
                        override = Override(
                            team_name=rec.team_name,
                            sheet_name=rec.sheet_name,
                            original_recommendation=rec.recommendation_type,
                            original_grade=rec.current_grade,
                            admin_decision=f"override to {new_grade}",
                            final_grade=new_grade,
                            reason=reason,
                            season=season,
                        )
                        override_manager.record_override(override)
                        st.success(f"Grade overridden to {new_grade}.")
                        st.session_state[f"show_override_{key_suffix}"] = False
                        st.rerun()
                    else:
                        st.error("Please provide grade and reason.")


def _export_recommendations(recommendations: list[Recommendation]) -> None:
    """Export recommendations to Excel.

    Args:
        recommendations: Recommendations to export.
    """
    import io

    rows = []
    for rec in recommendations:
        rec_type = rec.recommendation_type.value if hasattr(rec.recommendation_type, "value") else str(rec.recommendation_type)
        conf_val = rec.confidence.value if hasattr(rec.confidence, "value") else str(rec.confidence)
        rows.append(
            {
                "Team": rec.team_name,
                "Current Grade": rec.current_grade,
                "Recommended Grade": rec.recommended_grade,
                "Recommendation": rec_type,
                "Confidence": conf_val,
                "Explanation": rec.explanation,
                "Evidence": "; ".join(rec.evidence),
                "Concerns": "; ".join(rec.concerns),
                "SoS Note": rec.strength_of_schedule_note or "",
            }
        )

    df = pd.DataFrame(rows)
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Recommendations")

    st.download_button(
        label="📥 Download Excel",
        data=buffer.getvalue(),
        file_name=f"recommendations_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
