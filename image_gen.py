import os
import io
import random
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from models import PlayerStats, ClubStats

class ImageGenerator:
    def __init__(self, assets_dir: str = "assets"):
        self.assets_dir = assets_dir
        self.fonts_dir = os.path.join(assets_dir, "fonts")
        self.bg_dir = os.path.join(assets_dir, "backgrounds")
        self.players_dir = os.path.join(assets_dir, "players")
        
        # Default colors
        self.GOLD = (255, 215, 0)
        self.SILVER = (192, 192, 192)
        self.BRONZE = (205, 127, 50)
        self.WHITE = (255, 255, 255)
        self.BLACK = (0, 0, 0)
        self.RED = (220, 20, 60)
        self.GREEN = (50, 205, 50)
        self.ORANGE = (255, 140, 0)
        self.BLUE = (30, 144, 255)
        self.DARK_BG = (15, 15, 25)
        self.CARD_BG = (25, 25, 40)
    
    def _get_font(self, size: int, bold: bool = False):
        # Try multiple font paths
        candidates = [
            os.path.join(self.fonts_dir, "Cairo-Bold.ttf" if bold else "Cairo-Regular.ttf"),
            os.path.join(self.fonts_dir, "NotoSansArabic-Bold.ttf" if bold else "NotoSansArabic-Regular.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()
    
    def _create_gradient_bg(self, size: Tuple[int, int], color1: Tuple, color2: Tuple) -> Image:
        img = Image.new('RGB', size)
        draw = ImageDraw.Draw(img)
        for y in range(size[1]):
            r = int(color1[0] + (color2[0] - color1[0]) * y / size[1])
            g = int(color1[1] + (color2[1] - color1[1]) * y / size[1])
            b = int(color1[2] + (color2[2] - color1[2]) * y / size[1])
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))
        return img
    
    def _add_glow(self, draw, pos, radius, color, intensity=0.3):
        # Simplified glow effect
        pass
    
    def _draw_stat_bar(self, draw, x, y, width, height, value, max_val, color, bg_color=(40, 40, 55)):
        # Background
        draw.rectangle([x, y, x + width, y + height], fill=bg_color, outline=(60, 60, 75), width=1)
        # Fill
        fill_width = int((value / max_val) * width) if max_val > 0 else 0
        if fill_width > 0:
            draw.rectangle([x, y, x + fill_width, y + height], fill=color)
    
    def _get_player_color(self, player: PlayerStats) -> Tuple:
        if player.impact_score > 80:
            return self.GOLD
        elif player.impact_score > 60:
            return self.SILVER
        elif player.impact_score > 40:
            return self.BLUE
        else:
            return self.RED
    
    def generate_player_card(self, player: PlayerStats, position: str = "CM", 
                            club_name: str = "Rachad L3ERGONI") -> io.BytesIO:
        W, H = 600, 900
        img = self._create_gradient_bg((W, H), (20, 20, 35), (10, 10, 20))
        draw = ImageDraw.Draw(img)
        
        # Decorative elements
        draw.rectangle([20, 20, W-20, H-20], outline=(255, 255, 255, 50), width=2)
        
        # Club name at top
        font_small = self._get_font(20)
        font_medium = self._get_font(28, bold=True)
        font_large = self._get_font(42, bold=True)
        font_stat = self._get_font(22)
        
        # Header
        draw.text((W//2, 50), club_name, fill=self.WHITE, font=font_medium, anchor="mm")
        draw.text((W//2, 90), f"Division {6} • Pro Clubs Tracker", fill=self.SILVER, font=font_small, anchor="mm")
        
        # Player name
        draw.text((W//2, 160), player.name, fill=self.GOLD, font=font_large, anchor="mm")
        draw.text((W//2, 210), position.upper(), fill=self.SILVER, font=font_medium, anchor="mm")
        
        # Rating circle
        rating_color = self.GREEN if player.rating_pg >= 7 else self.ORANGE if player.rating_pg >= 5 else self.RED
        draw.ellipse([W//2-60, 250, W//2+60, 370], fill=rating_color, outline=self.WHITE, width=3)
        draw.text((W//2, 310), str(round(player.rating_pg, 1)), fill=self.WHITE, font=font_large, anchor="mm")
        
        # Stats section
        y_start = 400
        stats = [
            ("Games", player.games, 100, self.WHITE),
            ("Goals", player.goals, 50, self.GREEN),
            ("Assists", player.assists, 50, self.BLUE),
            ("Pass %", round(player.pass_accuracy, 1), 100, self.ORANGE),
            ("Tackles", player.tackles, 50, self.SILVER),
            ("Interceptions", player.interceptions, 50, self.SILVER),
            ("Poss Lost", player.possession_losses, 50, self.RED),
            ("MOTM", player.motm, 20, self.GOLD),
        ]
        
        for i, (label, val, max_v, color) in enumerate(stats):
            y = y_start + i * 55
            draw.text((40, y), label, fill=self.SILVER, font=font_stat)
            self._draw_stat_bar(draw, 200, y, 300, 30, val, max_v, color)
            draw.text((520, y), str(val), fill=self.WHITE, font=font_stat)
        
        # Advanced metrics
        y_adv = y_start + len(stats) * 55 + 30
        draw.text((W//2, y_adv), "ADVANCED METRICS", fill=self.GOLD, font=font_medium, anchor="mm")
        
        adv_stats = [
            ("Impact", round(player.impact_score, 1)),
            ("Clutch", round(player.clutch_score, 1)),
            ("Error", round(player.error_score, 1)),
            ("Throwing", round(player.throwing_score, 1)),
        ]
        
        for i, (label, val) in enumerate(adv_stats):
            x = 80 + (i % 2) * 250
            y = y_adv + 40 + (i // 2) * 50
            color = self.RED if label in ["Error", "Throwing"] and val > 5 else self.GREEN
            draw.text((x, y), f"{label}: {val}", fill=color, font=font_stat)
        
        # Footer
        draw.text((W//2, H-40), "Rachad L3ERGONI Bot • ProClubsTracker", fill=(100, 100, 120), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def generate_motm_card(self, player: PlayerStats, position: str = "CM") -> io.BytesIO:
        W, H = 600, 800
        img = self._create_gradient_bg((W, H), (40, 30, 10), (20, 15, 5))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(48, bold=True)
        font_medium = self._get_font(32, bold=True)
        font_small = self._get_font(22)
        
        # MOTM Header
        draw.text((W//2, 80), "MAN OF THE MATCH", fill=self.GOLD, font=font_large, anchor="mm")
        draw.text((W//2, 140), "★ ★ ★", fill=self.GOLD, font=font_medium, anchor="mm")
        
        # Player
        draw.text((W//2, 220), player.name, fill=self.WHITE, font=font_large, anchor="mm")
        draw.text((W//2, 280), position.upper(), fill=self.SILVER, font=font_medium, anchor="mm")
        
        # Big rating
        draw.ellipse([W//2-80, 320, W//2+80, 480], fill=self.GOLD, outline=self.WHITE, width=4)
        draw.text((W//2, 400), str(round(player.rating_pg, 1)), fill=self.BLACK, font=font_large, anchor="mm")
        
        # Key stats
        stats_y = 520
        draw.text((W//2, stats_y), f"Goals: {player.goals}  |  Assists: {player.assists}", 
                 fill=self.WHITE, font=font_medium, anchor="mm")
        draw.text((W//2, stats_y+50), f"Impact: {round(player.impact_score, 1)}  |  Clutch: {round(player.clutch_score, 1)}", 
                 fill=self.SILVER, font=font_small, anchor="mm")
        
        draw.text((W//2, H-60), "Rachad L3ERGONI • MOTM", fill=(150, 150, 150), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def generate_roast_card(self, player: PlayerStats, roast_text: str, position: str = "CM") -> io.BytesIO:
        W, H = 700, 500
        img = self._create_gradient_bg((W, H), (35, 10, 10), (20, 5, 5))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(36, bold=True)
        font_medium = self._get_font(24)
        font_roast = self._get_font(20)
        
        # Header
        draw.text((W//2, 50), "ROAST REPORT", fill=self.RED, font=font_large, anchor="mm")
        draw.text((W//2, 100), f"{player.name} • {position.upper()}", fill=self.WHITE, font=font_medium, anchor="mm")
        
        # Rating badge
        rating_color = self.RED if player.rating_pg < 5 else self.ORANGE if player.rating_pg < 7 else self.GREEN
        draw.rounded_rectangle([50, 140, 150, 240], radius=10, fill=rating_color)
        draw.text((100, 190), str(round(player.rating_pg, 1)), fill=self.WHITE, font=font_large, anchor="mm")
        
        # Stats column
        stats = [
            f"Goals: {player.goals}",
            f"Assists: {player.assists}",
            f"Pass: {round(player.pass_accuracy, 1)}%",
            f"Poss Lost: {player.possession_losses}",
            f"Impact: {round(player.impact_score, 1)}",
            f"Throwing: {round(player.throwing_score, 1)}",
        ]
        for i, s in enumerate(stats):
            draw.text((180, 150 + i * 30), s, fill=self.SILVER, font=font_roast)
        
        # Roast text box
        draw.rounded_rectangle([50, 280, W-50, H-50], radius=15, fill=(30, 10, 10), outline=self.RED, width=2)
        
        # Wrap text
        words = roast_text.split()
        lines = []
        line = []
        for word in words:
            line.append(word)
            if len(" ".join(line)) > 50:
                lines.append(" ".join(line[:-1]))
                line = [line[-1]]
        if line:
            lines.append(" ".join(line))
        
        y = 310
        for line in lines[:8]:  # Max 8 lines
            draw.text((W//2, y), line, fill=self.WHITE, font=font_roast, anchor="mm")
            y += 28
        
        draw.text((W//2, H-25), "Rachad L3ERGONI Bot", fill=(100, 100, 100), font=font_roast, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def generate_leaderboard(self, players: List[PlayerStats], metric: str = "impact_score") -> io.BytesIO:
        W, H = 800, 600 + len(players) * 60
        img = self._create_gradient_bg((W, H), (15, 15, 25), (10, 10, 15))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(36, bold=True)
        font_medium = self._get_font(24, bold=True)
        font_small = self._get_font(20)
        
        # Title
        draw.text((W//2, 40), f"LEADERBOARD — {metric.upper().replace('_', ' ')}", 
                 fill=self.GOLD, font=font_large, anchor="mm")
        
        # Headers
        headers = ["#", "Player", "Games", "Goals", "Assists", "Rating", metric.replace('_', ' ').title()]
        x_positions = [40, 100, 280, 380, 480, 580, 680]
        
        for i, h in enumerate(headers):
            draw.text((x_positions[i], 100), h, fill=self.SILVER, font=font_medium)
        
        # Sort players
        sorted_players = sorted(players, key=lambda p: getattr(p, metric, 0), reverse=True)
        
        for idx, p in enumerate(sorted_players[:10]):
            y = 150 + idx * 55
            color = self.GOLD if idx == 0 else self.SILVER if idx == 1 else self.BRONZE if idx == 2 else self.WHITE
            
            # Rank
            draw.text((x_positions[0], y), str(idx+1), fill=color, font=font_medium)
            # Name
            draw.text((x_positions[1], y), p.name[:15], fill=self.WHITE, font=font_small)
            # Stats
            draw.text((x_positions[2], y), str(p.games), fill=self.SILVER, font=font_small)
            draw.text((x_positions[3], y), str(p.goals), fill=self.SILVER, font=font_small)
            draw.text((x_positions[4], y), str(p.assists), fill=self.SILVER, font=font_small)
            draw.text((x_positions[5], y), str(round(p.rating_pg, 1)), fill=self.SILVER, font=font_small)
            draw.text((x_positions[6], y), str(round(getattr(p, metric, 0), 1)), fill=color, font=font_small)
            
            # Separator
            draw.line([(40, y+35), (W-40, y+35)], fill=(40, 40, 50), width=1)
        
        draw.text((W//2, H-30), "Rachad L3ERGONI Bot • ProClubsTracker", fill=(80, 80, 90), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    def generate_match_report(self, club: ClubStats, motm: PlayerStats) -> io.BytesIO:
        W, H = 800, 700
        img = self._create_gradient_bg((W, H), (20, 25, 35), (10, 15, 20))
        draw = ImageDraw.Draw(img)
        
        font_large = self._get_font(40, bold=True)
        font_medium = self._get_font(28, bold=True)
        font_small = self._get_font(20)
        
        # Header
        draw.text((W//2, 50), club.club_name, fill=self.WHITE, font=font_large, anchor="mm")
        draw.text((W//2, 100), f"Division {club.division} • Skill Rating {club.skill_rating}", 
                 fill=self.SILVER, font=font_small, anchor="mm")
        
        # Record
        draw.text((W//2, 160), f"{club.wins}W — {club.losses}L — {club.draws}D", 
                 fill=self.GOLD, font=font_medium, anchor="mm")
        
        # Win rate bar
        total = club.wins + club.losses + club.draws
        if total > 0:
            win_pct = club.wins / total
            draw.rectangle([100, 220, 700, 260], fill=(40, 40, 50))
            draw.rectangle([100, 220, 100 + int(600 * win_pct), 260], fill=self.GREEN)
            draw.text((W//2, 240), f"Win Rate: {round(win_pct*100, 1)}%", fill=self.WHITE, font=font_small, anchor="mm")
        
        # MOTM
        draw.text((W//2, 300), "MVP OF THE SEASON", fill=self.GOLD, font=font_medium, anchor="mm")
        draw.text((W//2, 350), motm.name, fill=self.WHITE, font=font_large, anchor="mm")
        draw.text((W//2, 400), f"Impact: {round(motm.impact_score, 1)} • Clutch: {round(motm.clutch_score, 1)}", 
                 fill=self.SILVER, font=font_small, anchor="mm")
        
        # Top stats
        top_scorer = max(club.players, key=lambda p: p.goals) if club.players else None
        top_assist = max(club.players, key=lambda p: p.assists) if club.players else None
        top_def = max(club.players, key=lambda p: p.tackles + p.interceptions) if club.players else None
        
        y = 460
        if top_scorer:
            draw.text((W//2, y), f"Top Scorer: {top_scorer.name} ({top_scorer.goals} goals)", 
                     fill=self.GREEN, font=font_small, anchor="mm")
            y += 35
        if top_assist:
            draw.text((W//2, y), f"Top Assists: {top_assist.name} ({top_assist.assists} assists)", 
                     fill=self.BLUE, font=font_small, anchor="mm")
            y += 35
        if top_def:
            draw.text((W//2, y), f"Top Defender: {top_def.name} ({top_def.tackles} T, {top_def.interceptions} INT)", 
                     fill=self.SILVER, font=font_small, anchor="mm")
        
        draw.text((W//2, H-40), "Rachad L3ERGONI Bot • ProClubsTracker", fill=(80, 80, 90), font=font_small, anchor="mm")
        
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
