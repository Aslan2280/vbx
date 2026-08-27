# database.py
import sqlite3
from datetime import datetime, timedelta
import random
from typing import Optional, List, Dict
from contextlib import contextmanager

class Database:
    def __init__(self, db_path='bot_database.db'):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    display_name TEXT,
                    balance INTEGER DEFAULT 100,
                    total_wins INTEGER DEFAULT 0,
                    total_games INTEGER DEFAULT 0,
                    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    chat_id INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS farms (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    farm_number INTEGER,
                    level INTEGER DEFAULT 1,
                    income_boost BOOLEAN DEFAULT 0,
                    anti_hack BOOLEAN DEFAULT 0,
                    auto_collect BOOLEAN DEFAULT 0,
                    last_collected TIMESTAMP,
                    collected_amount INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS deposits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    amount INTEGER,
                    days INTEGER,
                    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_date TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS achievements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    achievement_type TEXT,
                    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jackpot (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS duels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    challenger_id INTEGER,
                    opponent_id INTEGER,
                    amount INTEGER,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    FOREIGN KEY (challenger_id) REFERENCES users (user_id),
                    FOREIGN KEY (opponent_id) REFERENCES users (user_id)
                )
            ''')
            
            cursor.execute('INSERT OR IGNORE INTO jackpot (id, amount) VALUES (1, 0)')
            
            try:
                cursor.execute('ALTER TABLE users ADD COLUMN chat_id INTEGER DEFAULT 0')
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute('ALTER TABLE farms ADD COLUMN last_collected TIMESTAMP')
            except sqlite3.OperationalError:
                pass
            
            conn.commit()
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def create_user(self, user_id: int, username: str = None, chat_id: int = 0) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            display_name = username or f'User{user_id}'
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, display_name, balance, chat_id)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, display_name, 100, chat_id))
            conn.commit()
            return self.get_user(user_id)
    
    def update_balance(self, user_id: int, amount: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            ''', (amount, user_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_balance(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            return row['balance'] if row else 0
    
    def update_last_active(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET last_active = CURRENT_TIMESTAMP 
                WHERE user_id = ?
            ''', (user_id,))
            conn.commit()
    
    def change_display_name(self, user_id: int, new_name: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET display_name = ? 
                WHERE user_id = ?
            ''', (new_name, user_id))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_top_users(self, limit: int = 10) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, display_name, balance, total_wins 
                FROM users 
                ORDER BY balance DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_profile(self, user_id: int) -> Dict:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, display_name, balance, total_wins, total_games,
                       registered_at, last_active
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            if not row:
                return {}
            
            profile = dict(row)
            
            cursor.execute('''
                SELECT achievement_type 
                FROM achievements 
                WHERE user_id = ?
            ''', (user_id,))
            profile['achievements'] = [row['achievement_type'] for row in cursor.fetchall()]
            
            cursor.execute('SELECT COUNT(*) as count FROM farms WHERE user_id = ?', (user_id,))
            profile['farm_count'] = cursor.fetchone()['count']
            
            return profile
    
    def get_user_farms(self, user_id: int) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM farms 
                WHERE user_id = ? 
                ORDER BY farm_number
            ''', (user_id,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_farm_count(self, user_id: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM farms WHERE user_id = ?', (user_id,))
            return cursor.fetchone()['count']
    
    def buy_farm(self, user_id: int) -> bool:
        farm_count = self.get_farm_count(user_id)
        if farm_count >= 5:
            return False
        
        cost = 500 + (farm_count * 200)
        balance = self.get_balance(user_id)
        
        if balance < cost:
            return False
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users 
                SET balance = balance - ? 
                WHERE user_id = ?
            ''', (cost, user_id))
            
            cursor.execute('''
                INSERT INTO farms (user_id, farm_number, last_collected)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (user_id, farm_count + 1))
            conn.commit()
            return True
    
    def upgrade_farm(self, user_id: int, farm_number: int, upgrade_type: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM farms 
                WHERE user_id = ? AND farm_number = ?
            ''', (user_id, farm_number))
            farm = cursor.fetchone()
            
            if not farm:
                return False
            
            if upgrade_type == 'бустер' and farm['income_boost']:
                return False
            elif upgrade_type == 'защита' and farm['anti_hack']:
                return False
            elif upgrade_type == 'автосбор' and farm['auto_collect']:
                return False
            
            costs = {
                'бустер': 300,
                'защита': 150,
                'автосбор': 400
            }
            
            cost = costs.get(upgrade_type)
            if not cost:
                return False
            
            balance = self.get_balance(user_id)
            if balance < cost:
                return False
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance - ? 
                WHERE user_id = ?
            ''', (cost, user_id))
            
            columns = {
                'бустер': 'income_boost',
                'защита': 'anti_hack',
                'автосбор': 'auto_collect'
            }
            
            cursor.execute(f'''
                UPDATE farms 
                SET {columns[upgrade_type]} = 1 
                WHERE user_id = ? AND farm_number = ?
            ''', (user_id, farm_number))
            
            conn.commit()
            return True
    
    def collect_farm_income(self, user_id: int, farm_number: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM farms 
                WHERE user_id = ? AND farm_number = ?
            ''', (user_id, farm_number))
            farm = cursor.fetchone()
            
            if not farm:
                return 0
            
            cursor.execute('''
                SELECT last_active 
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return 0
            
            last_active = datetime.strptime(user['last_active'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() - last_active > timedelta(hours=2):
                if not farm['auto_collect']:
                    return 0
            
            base_income = random.randint(5, 20)
            
            if farm['income_boost']:
                base_income = int(base_income * 1.5)
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            ''', (base_income, user_id))
            
            cursor.execute('''
                UPDATE farms 
                SET last_collected = CURRENT_TIMESTAMP,
                    collected_amount = collected_amount + ?
                WHERE user_id = ? AND farm_number = ?
            ''', (base_income, user_id, farm_number))
            
            conn.commit()
            return base_income
    
    def protect_all_farms(self, user_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            farms = self.get_user_farms(user_id)
            if not farms:
                return False
            
            cost = 30 * len(farms)
            balance = self.get_balance(user_id)
            
            if balance < cost:
                return False
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance - ? 
                WHERE user_id = ?
            ''', (cost, user_id))
            
            cursor.execute('''
                UPDATE farms 
                SET anti_hack = 1 
                WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            return True
    
    def create_deposit(self, user_id: int, amount: int, days: int) -> bool:
        balance = self.get_balance(user_id)
        if balance < amount:
            return False
        
        if amount < 100 or days < 1 or days > 7:
            return False
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance - ? 
                WHERE user_id = ?
            ''', (amount, user_id))
            
            end_date = datetime.now() + timedelta(days=days)
            cursor.execute('''
                INSERT INTO deposits (user_id, amount, days, end_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, amount, days, end_date.strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            return True
    
    def get_active_deposit(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM deposits 
                WHERE user_id = ? AND is_active = 1
            ''', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def close_deposit(self, user_id: int) -> Optional[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM deposits 
                WHERE user_id = ? AND is_active = 1
            ''', (user_id,))
            deposit = cursor.fetchone()
            
            if not deposit:
                return None
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            ''', (deposit['amount'], user_id))
            
            cursor.execute('''
                UPDATE deposits 
                SET is_active = 0 
                WHERE id = ?
            ''', (deposit['id'],))
            
            conn.commit()
            return deposit['amount']
    
    def process_deposits(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM deposits 
                WHERE is_active = 1 AND end_date <= CURRENT_TIMESTAMP
            ''')
            deposits = cursor.fetchall()
            
            for deposit in deposits:
                profit = int(deposit['amount'] * 0.05 * deposit['days'])
                total = deposit['amount'] + profit
                
                cursor.execute('''
                    UPDATE users 
                    SET balance = balance + ? 
                    WHERE user_id = ?
                ''', (total, deposit['user_id']))
                
                cursor.execute('''
                    UPDATE deposits 
                    SET is_active = 0 
                    WHERE id = ?
                ''', (deposit['id'],))
            
            conn.commit()
            return len(deposits)
    
    def add_game_result(self, user_id: int, win: bool, amount: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE users 
                SET total_games = total_games + 1,
                    total_wins = total_wins + ? 
                WHERE user_id = ?
            ''', (1 if win else 0, user_id))
            
            if win:
                cursor.execute('''
                    UPDATE users 
                    SET balance = balance + ? 
                    WHERE user_id = ?
                ''', (amount, user_id))
            
            conn.commit()
    
    def get_jackpot(self) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT amount FROM jackpot WHERE id = 1')
            row = cursor.fetchone()
            return row['amount'] if row else 0
    
    def update_jackpot(self, amount: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jackpot 
                SET amount = amount + ? 
                WHERE id = 1
            ''', (amount,))
            conn.commit()
    
    def reset_jackpot(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE jackpot SET amount = 0 WHERE id = 1')
            conn.commit()
    
    def create_duel(self, challenger_id: int, opponent_id: int, amount: int) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            expires_at = datetime.now() + timedelta(seconds=30)
            cursor.execute('''
                INSERT INTO duels (challenger_id, opponent_id, amount, expires_at)
                VALUES (?, ?, ?, ?)
            ''', (challenger_id, opponent_id, amount, expires_at.strftime('%Y-%m-%d %H:%M:%S')))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_duel(self, duel_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM duels 
                WHERE id = ? AND status = 'pending'
            ''', (duel_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_pending_duel(self, user_id: int) -> Optional[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM duels 
                WHERE (challenger_id = ? OR opponent_id = ?) 
                AND status = 'pending'
                AND expires_at > CURRENT_TIMESTAMP
            ''', (user_id, user_id))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def accept_duel(self, duel_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE duels 
                SET status = 'accepted' 
                WHERE id = ? AND status = 'pending'
            ''', (duel_id,))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def complete_duel(self, duel_id: int, winner_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM duels WHERE id = ?', (duel_id,))
            duel = cursor.fetchone()
            
            if not duel:
                return False
            
            commission = int(duel['amount'] * 0.05)
            prize = duel['amount'] * 2 - commission
            
            cursor.execute('''
                UPDATE users 
                SET balance = balance + ? 
                WHERE user_id = ?
            ''', (prize, winner_id))
            
            cursor.execute('''
                UPDATE users 
                SET total_wins = total_wins + 1,
                    total_games = total_games + 1 
                WHERE user_id = ?
            ''', (winner_id,))
            
            loser_id = duel['opponent_id'] if winner_id == duel['challenger_id'] else duel['challenger_id']
            cursor.execute('''
                UPDATE users 
                SET total_games = total_games + 1 
                WHERE user_id = ?
            ''', (loser_id,))
            
            cursor.execute('''
                UPDATE duels 
                SET status = 'completed' 
                WHERE id = ?
            ''', (duel_id,))
            
            conn.commit()
            return True
    
    def expire_duels(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE duels 
                SET status = 'expired' 
                WHERE status = 'pending' 
                AND expires_at <= CURRENT_TIMESTAMP
            ''')
            conn.commit()
    
    def check_achievements(self, user_id: int):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT balance, total_wins, total_games 
                FROM users 
                WHERE user_id = ?
            ''', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                return []
            
            achievements = []
            
            if user['total_games'] >= 10:
                cursor.execute('''
                    INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                    VALUES (?, '10_duels')
                ''', (user_id,))
                if cursor.rowcount > 0:
                    achievements.append('10_duels')
            
            if user['balance'] >= 1000:
                cursor.execute('''
                    INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                    VALUES (?, '1000_coins')
                ''', (user_id,))
                if cursor.rowcount > 0:
                    achievements.append('1000_coins')
            
            if user['total_wins'] >= 1:
                cursor.execute('''
                    INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                    VALUES (?, 'first_win')
                ''', (user_id,))
                if cursor.rowcount > 0:
                    achievements.append('first_win')
            
            cursor.execute('SELECT COUNT(*) as count FROM farms WHERE user_id = ?', (user_id,))
            farm_count = cursor.fetchone()['count']
            if farm_count >= 1:
                cursor.execute('''
                    INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                    VALUES (?, 'first_farm')
                ''', (user_id,))
                if cursor.rowcount > 0:
                    achievements.append('first_farm')
            
            cursor.execute('SELECT COUNT(*) as count FROM deposits WHERE user_id = ? AND is_active = 0', (user_id,))
            deposit_count = cursor.fetchone()['count']
            if deposit_count >= 1:
                cursor.execute('''
                    INSERT OR IGNORE INTO achievements (user_id, achievement_type)
                    VALUES (?, 'first_deposit')
                ''', (user_id,))
                if cursor.rowcount > 0:
                    achievements.append('first_deposit')
            
            conn.commit()
            return achievements
    
    def get_user_achievements(self, user_id: int) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT achievement_type 
                FROM achievements 
                WHERE user_id = ?
            ''', (user_id,))
            return [row['achievement_type'] for row in cursor.fetchall()]
