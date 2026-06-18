"""
image_gen_ecosystem.py — PHASE 4 Image Generators (Standalone)
================================================================
Completely standalone. No imports from image_gen.py.
Generates: Match Posters, Hall cards, Rivalry cards, Milestone cards, Weekly Awards cards.
"""

import io
import os
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import List, Optional, Dict

CARD_W, CARD_H = 1440, 2160
MARGIN = 80

def _gradient_bg(w, h, c1, c2):
    img = Image.new("RGB", (w, h), c1)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        ratio = y / h
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img

def _glow_circle(img, cx, cy, radius, color, intensity=0.35):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for r in range(radius, 0, -30):
        alpha = int(200 * intensity * (r / radius))
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(*color, max(0, alpha // 4)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)

def _load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

def _load_player_photo(name, assets_dir, max_size=(1600, 1600), photo_path=None):
    def _try_load(path):
        if not path or not os.path.exists(path):
            return None
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail(max_size, Image.LANCZOS)
            return img
        except Exception:
            return None
    img = _try_load(photo_path)
    if img: return img
    clean = name.replace(" ", "_").lower()
    upper = name.upper()
    title = name.title()
    candidates = [
        os.path.join(assets_dir, f"{name}.png"), os.path.join(assets_dir, f"{name}.jpg"), os.path.join(assets_dir, f"{name}.jpeg"),
        os.path.join(assets_dir, f"{clean}.png"), os.path.join(assets_dir, f"{clean}.jpg"), os.path.join(assets_dir, f"{clean}.jpeg"),
        os.path.join(assets_dir, f"{upper}.png"), os.path.join(assets_dir, f"{upper}.jpg"), os.path.join(assets_dir, f"{upper}.jpeg"),
        os.path.join(assets_dir, f"{title}.png"), os.path.join(assets_dir, f"{title}.jpg"), os.path.join(assets_dir, f"{title}.jpeg"),
    ]
    for path in candidates:
        img = _try_load(path)
        if img: return img
    return None


# ─── MATCH POSTER ───
def generate_match_poster(assets_dir, poster_data, photo_paths=None):
    pal = {"bg_top": (5, 5, 8), "bg_bot": (15, 12, 25), "accent": (255, 215, 0), "accent2": (218, 165, 32),
           "glow": (255, 200, 50), "text": (255, 248, 220), "text_dim": (180, 170, 160),
           "red": (255, 50, 50), "green": (50, 255, 100), "purple": (186, 85, 211), "blue": (0, 191, 255)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 4, 900, pal["glow"], 0.15)
    draw = ImageDraw.Draw(img)
    photo_paths = photo_paths or {}

    f_title = _load_font(100, bold=True)
    result = poster_data.get("result", "D")
    result_color = pal["green"] if result == "W" else pal["red"] if result == "L" else pal["accent"]
    draw.text((W // 2, 80), "MATCH RESULT", fill=pal["text_dim"], font=_load_font(50), anchor="mm")
    draw.text((W // 2, 180), f"{poster_data['score']} vs {poster_data['opponent']}", fill=result_color, font=f_title, anchor="mm")

    awards = []
    if poster_data.get("mvp"): awards.append(("🏆 MVP", poster_data["mvp"]["name"], pal["accent"], poster_data["mvp"]["player_obj"]))
    if poster_data.get("fraud"): awards.append(("🎭 FRAUD", poster_data["fraud"]["name"], pal["red"], poster_data["fraud"]["player_obj"]))
    if poster_data.get("ghost") and poster_data["ghost"]["is_ghost"]: awards.append(("👻 GHOST", poster_data["ghost"]["name"], pal["purple"], poster_data["ghost"]["player_obj"]))
    if poster_data.get("carry"): awards.append(("💪 CARRY", poster_data["carry"]["name"], pal["green"], poster_data["carry"]["player_obj"]))
    if poster_data.get("top_performer"): awards.append(("⭐ TOP", poster_data["top_performer"]["name"], pal["blue"], poster_data["top_performer"]["player_obj"]))
    if poster_data.get("worst_performer"): awards.append(("📉 WORST", poster_data["worst_performer"]["name"], pal["red"], poster_data["worst_performer"]["player_obj"]))

    card_w = (W - MARGIN * 3) // 2
    card_h = 320
    start_y = 320
    f_award = _load_font(36, bold=True)
    f_name = _load_font(48, bold=True)
    f_stat = _load_font(32)

    for i, (label, name, color, player_obj) in enumerate(awards):
        col = i % 2; row = i // 2
        x = MARGIN + col * (card_w + MARGIN)
        y = start_y + row * (card_h + 30)
        draw.rounded_rectangle([x, y, x + card_w, y + card_h], radius=25, fill=(25, 25, 30, 220), outline=(*color, 150), width=3)
        draw.text((x + 30, y + 20), label, fill=color, font=f_award)
        draw.text((x + 30, y + 80), name, fill=pal["text"], font=f_name)
        if player_obj:
            sq = getattr(player_obj, "_squad_info", {}) or {}
            raw_img = sq.get("image")
            ppath = photo_paths.get(name) or raw_img
            photo = _load_player_photo(name, assets_dir, max_size=(200, 200), photo_path=ppath)
            if photo:
                px = x + card_w - 220; py = y + 20
                img.paste(photo, (px, py), photo)
            rating = round(getattr(player_obj, "rating_pg", 0), 1)
            draw.text((x + 30, y + 160), f"Rating: {rating} | Impact: {getattr(player_obj, 'impact_score', 0)}", fill=pal["text_dim"], font=f_stat)

    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • MATCH POSTER", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf


# ─── HALL OF SHAME CARD ───
def generate_hall_of_shame_card(assets_dir, records, club_name):
    pal = {"bg_top": (18, 4, 4), "bg_bot": (45, 8, 8), "accent": (255, 50, 50), "text": (255, 230, 230), "text_dim": (210, 150, 150)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 3, 800, pal["accent"], 0.25)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, 80), "🏛️ HALL OF SHAME", fill=pal["accent"], font=_load_font(100, bold=True), anchor="mm")
    draw.text((W // 2, 180), club_name.upper(), fill=pal["text_dim"], font=_load_font(48), anchor="mm")

    row_h = 260; start_y = 280
    emojis = {"worst_rating_ever": "📉", "most_possession_lost_ever": "💀", "biggest_fraud_performance": "🎭",
              "worst_pass_accuracy_ever": "🎯", "most_missed_chances_ever": "❌", "biggest_ghost_performance": "👻",
              "worst_carry_score_ever": "🎒"}
    labels = {"worst_rating_ever": "Worst Rating Ever", "most_possession_lost_ever": "Most Possession Lost Ever",
              "biggest_fraud_performance": "Biggest Fraud Performance", "worst_pass_accuracy_ever": "Worst Pass Accuracy Ever",
              "most_missed_chances_ever": "Most Missed Chances Ever", "biggest_ghost_performance": "Biggest Ghost Performance",
              "worst_carry_score_ever": "Worst Carry Score Ever"}
    for i, rec in enumerate(records[:7]):
        y = start_y + i * row_h
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=20, fill=(35, 10, 10, 200), outline=(*pal["accent"], 100), width=2)
        emoji = emojis.get(rec.category, "🔥"); label = labels.get(rec.category, rec.category)
        draw.text((MARGIN + 30, y + 20), f"{emoji} {label}", fill=pal["accent"], font=_load_font(36, bold=True))
        draw.text((MARGIN + 30, y + 80), f"{rec.player_name} — {rec.description}", fill=pal["text"], font=_load_font(40, bold=True))
        if rec.date: draw.text((MARGIN + 30, y + 150), f"📅 {rec.date}", fill=pal["text_dim"], font=_load_font(30))
    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • SHAME ETERNAL", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf


# ─── HALL OF FAME CARD ───
def generate_hall_of_fame_card(assets_dir, records, club_name):
    pal = {"bg_top": (10, 8, 4), "bg_bot": (30, 22, 8), "accent": (255, 215, 0), "text": (255, 248, 220), "text_dim": (200, 180, 140)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 3, 800, pal["accent"], 0.25)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, 80), "🏆 HALL OF FAME", fill=pal["accent"], font=_load_font(100, bold=True), anchor="mm")
    draw.text((W // 2, 180), club_name.upper(), fill=pal["text_dim"], font=_load_font(48), anchor="mm")

    row_h = 260; start_y = 280
    emojis = {"highest_rating_ever": "⭐", "most_goals_in_match": "⚽", "most_assists_in_match": "🅰️",
              "best_carry_performance": "💪", "best_defender_performance": "🛡️", "most_mvps_season": "🏆"}
    labels = {"highest_rating_ever": "Highest Rating Ever", "most_goals_in_match": "Most Goals in One Match",
              "most_assists_in_match": "Most Assists in One Match", "best_carry_performance": "Best Carry Performance",
              "best_defender_performance": "Best Defender Performance", "most_mvps_season": "Most MVPs This Season"}
    for i, rec in enumerate(records[:7]):
        y = start_y + i * row_h
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=20, fill=(30, 25, 10, 200), outline=(*pal["accent"], 100), width=2)
        emoji = emojis.get(rec.category, "👑"); label = labels.get(rec.category, rec.category)
        draw.text((MARGIN + 30, y + 20), f"{emoji} {label}", fill=pal["accent"], font=_load_font(36, bold=True))
        draw.text((MARGIN + 30, y + 80), f"{rec.player_name} — {rec.description}", fill=pal["text"], font=_load_font(40, bold=True))
        if rec.date: draw.text((MARGIN + 30, y + 150), f"📅 {rec.date}", fill=pal["text_dim"], font=_load_font(30))
    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • LEGENDS NEVER DIE", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf


# ─── RIVALRY CARD ───
def generate_rivalry_card(assets_dir, stats, p1_photo=None, p2_photo=None):
    pal = {"bg_top": (12, 4, 18), "bg_bot": (35, 10, 50), "accent": (186, 85, 211), "text": (245, 230, 255), "text_dim": (180, 150, 200), "green": (50, 255, 100)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 3, 900, pal["accent"], 0.2)
    draw = ImageDraw.Draw(img)
    p1 = stats["p1_name"]; p2 = stats["p2_name"]; winner = stats["overall_winner"]
    draw.text((W // 2, 80), "⚔️ RIVALRY", fill=pal["accent"], font=_load_font(90, bold=True), anchor="mm")
    draw.text((W // 2, 180), f"{p1}  vs  {p2}", fill=pal["text"], font=_load_font(70, bold=True), anchor="mm")

    p1_img = _load_player_photo(p1, assets_dir, max_size=(500, 500), photo_path=p1_photo)
    p2_img = _load_player_photo(p2, assets_dir, max_size=(500, 500), photo_path=p2_photo)
    if p1_img: img.paste(p1_img, (MARGIN + 50, 300), p1_img)
    if p2_img: img.paste(p2_img, (W - MARGIN - 50 - 500, 300), p2_img)
    draw.text((W // 2, 550), "VS", fill=pal["accent"], font=_load_font(80, bold=True), anchor="mm")

    start_y = 900; row_h = 110; f_stat = _load_font(38, bold=True); f_val = _load_font(42, bold=True)
    categories = [("Goals", "goals"), ("Assists", "assists"), ("Rating", "rating"), ("Win %", "win_rate"), ("Possession Lost", "possession_lost"), ("MOTM", "motm"), ("Impact", "impact")]
    for i, (label, key) in enumerate(categories):
        y = start_y + i * row_h
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 15], radius=15, fill=(25, 15, 35, 200), outline=(*pal["accent"], 80), width=2)
        v1 = stats[key]["p1"]; v2 = stats[key]["p2"]; w = stats[key]["winner"]
        c1 = pal["green"] if w == p1 else pal["text"]
        c2 = pal["green"] if w == p2 else pal["text"]
        draw.text((MARGIN + 40, y + 20), label, fill=pal["text_dim"], font=f_stat)
        draw.text((MARGIN + 300, y + 20), str(v1), fill=c1, font=f_val)
        draw.text((W // 2, y + 20), "—", fill=pal["text_dim"], font=f_val, anchor="mm")
        draw.text((W - MARGIN - 300, y + 20), str(v2), fill=c2, font=f_val)

    if winner != "Tie":
        banner_y = start_y + len(categories) * row_h + 40
        draw.rounded_rectangle([MARGIN, banner_y, W - MARGIN, banner_y + 140], radius=30, fill=(*pal["green"], 80), outline=pal["green"], width=4)
        draw.text((W // 2, banner_y + 70), f"🏆 WINNER: {winner}", fill=pal["text"], font=_load_font(80, bold=True), anchor="mm")
    else:
        banner_y = start_y + len(categories) * row_h + 40
        draw.rounded_rectangle([MARGIN, banner_y, W - MARGIN, banner_y + 140], radius=30, fill=(*pal["accent"], 60), outline=pal["accent"], width=4)
        draw.text((W // 2, banner_y + 70), "🤝 TIE", fill=pal["text"], font=_load_font(80, bold=True), anchor="mm")

    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • RIVALRY CENTRAL", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf


# ─── MILESTONE CARD ───
def generate_milestone_card(assets_dir, alert, player_photo=None):
    pal = {"bg_top": (4, 14, 6), "bg_bot": (8, 35, 14), "accent": (50, 255, 100), "text": (230, 255, 235), "text_dim": (150, 210, 170)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 3, 900, pal["accent"], 0.35)
    draw = ImageDraw.Draw(img)
    player = alert["player"]; stat = alert["stat"]; threshold = alert["threshold"]
    emojis = {"goals": "⚽", "assists": "🅰️", "mvps": "🏆", "frauds": "🎭", "possession_losses": "💀", "games": "🎮", "tackles": "🛡️"}
    emoji = emojis.get(stat, "🔥")
    draw.text((W // 2, 80), "🚨 MILESTONE ALERT", fill=pal["accent"], font=_load_font(80, bold=True), anchor="mm")
    draw.text((W // 2, 250), player.upper(), fill=pal["text"], font=_load_font(120, bold=True), anchor="mm")

    photo = _load_player_photo(player, assets_dir, max_size=(1000, 1000), photo_path=player_photo)
    if photo:
        px = (W - photo.width) // 2; py = 420
        shadow = Image.new("RGBA", (photo.width + 80, photo.height + 80), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle([20, 20, photo.width + 60, photo.height + 60], radius=40, fill=(*pal["accent"], 100))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=30))
        img.paste(shadow, (px - 40, py - 40), shadow)
        mask = Image.new("L", photo.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, photo.width, photo.height], radius=40, fill=255)
        img.paste(photo, (px, py), mask)

    draw.text((W // 2, 1500), f"{emoji} {threshold} {stat.upper()}", fill=pal["accent"], font=_load_font(90, bold=True), anchor="mm")
    draw.text((W // 2, 1650), "التاريخ كيتكتب اليوم. التاريخ ما كينساش.", fill=pal["text_dim"], font=_load_font(50), anchor="mm")
    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • MILESTONE TRACKER", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf


# ─── WEEKLY AWARDS CARD ───
def generate_weekly_awards_card(assets_dir, winners, week_date):
    pal = {"bg_top": (8, 8, 8), "bg_bot": (20, 20, 20), "accent": (180, 180, 180), "text": (240, 240, 240), "text_dim": (160, 160, 160), "red": (255, 50, 50), "green": (50, 255, 100), "purple": (186, 85, 211), "gold": (255, 215, 0)}
    W, H = CARD_W, CARD_H
    img = _gradient_bg(W, H, pal["bg_top"], pal["bg_bot"]).convert("RGBA")
    img = _glow_circle(img, W // 2, H // 3, 800, pal["accent"], 0.2)
    draw = ImageDraw.Draw(img)
    draw.text((W // 2, 80), "📅 WEEKLY AWARDS", fill=pal["gold"], font=_load_font(90, bold=True), anchor="mm")
    draw.text((W // 2, 180), week_date, fill=pal["text_dim"], font=_load_font(48), anchor="mm")

    award_colors = {"fraud_of_the_week": pal["red"], "ghost_of_the_week": pal["purple"], "mvp_of_the_week": pal["gold"],
                    "ball_loser_of_the_week": pal["red"], "carry_of_the_week": pal["green"]}
    row_h = 320; start_y = 280
    f_award = _load_font(40, bold=True); f_desc = _load_font(36); f_score = _load_font(50, bold=True)
    for i, w in enumerate(winners):
        y = start_y + i * row_h
        color = award_colors.get(w["award"], pal["accent"])
        draw.rounded_rectangle([MARGIN, y, W - MARGIN, y + row_h - 20], radius=25, fill=(30, 30, 30, 220), outline=(*color, 150), width=3)
        draw.text((MARGIN + 30, y + 20), w["title"], fill=color, font=f_award)
        draw.text((MARGIN + 30, y + 90), w["description"], fill=pal["text"], font=f_desc)
        draw.text((W - MARGIN - 30, y + 90), str(w["score"]), fill=color, font=f_score, anchor="rm")
    draw.text((W // 2, H - 60), "RACHAD L3ERGONI • WEEKLY AWARDS", fill=pal["text_dim"], font=_load_font(36), anchor="mm")
    img = img.convert("RGB")
    buf = io.BytesIO(); img.save(buf, format="PNG", optimize=True); buf.seek(0)
    return buf
