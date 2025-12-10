from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import sqlite3
from datetime import datetime
import json

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend-backend communication

# Database initialization
def init_db():
    conn = sqlite3.connect('padel.db')
    c = conn.cursor()
    
    # Create matches table
    c.execute('''CREATE TABLE IF NOT EXISTS matches
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  team1_player1 TEXT NOT NULL,
                  team1_player2 TEXT NOT NULL,
                  team2_player1 TEXT NOT NULL,
                  team2_player2 TEXT NOT NULL,
                  team1_sets INTEGER DEFAULT 0,
                  team2_sets INTEGER DEFAULT 0,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Create games table (for tracking individual games within sets)
    c.execute('''CREATE TABLE IF NOT EXISTS games
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  match_id INTEGER,
                  set_number INTEGER,
                  team1_games INTEGER,
                  team2_games INTEGER,
                  FOREIGN KEY (match_id) REFERENCES matches (id))''')
    
    # Create points table (for tracking point-by-point)
    c.execute('''CREATE TABLE IF NOT EXISTS points
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  match_id INTEGER,
                  set_number INTEGER,
                  game_number INTEGER,
                  team1_points INTEGER,
                  team2_points INTEGER,
                  timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (match_id) REFERENCES matches (id))''')
    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Helper function for database connections
def get_db():
    conn = sqlite3.connect('padel.db')
    conn.row_factory = sqlite3.Row  # Return dictionaries
    return conn

@app.route('/')
def index():
    return "Padel Score Tracker API is running!"

# Create a new match
@app.route('/api/matches', methods=['POST'])
def create_match():
    data = request.json
    
    required_fields = ['team1_player1', 'team1_player2', 'team2_player1', 'team2_player2']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''INSERT INTO matches 
                 (team1_player1, team1_player2, team2_player1, team2_player2)
                 VALUES (?, ?, ?, ?)''',
              (data['team1_player1'], data['team1_player2'],
               data['team2_player1'], data['team2_player2']))
    
    match_id = c.lastrowid
    
    # Initialize first set
    c.execute('''INSERT INTO games (match_id, set_number, team1_games, team2_games)
                 VALUES (?, 1, 0, 0)''', (match_id,))
    
    # Initialize first game in first set
    c.execute('''INSERT INTO points (match_id, set_number, game_number, team1_points, team2_points)
                 VALUES (?, 1, 1, 0, 0)''', (match_id,))
    
    conn.commit()
    
    match_data = c.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    conn.close()
    
    return jsonify(dict(match_data)), 201

# Get all matches
@app.route('/api/matches', methods=['GET'])
def get_matches():
    conn = get_db()
    c = conn.cursor()
    
    matches = c.execute('''
        SELECT m.*, 
               (SELECT MAX(set_number) FROM games WHERE match_id = m.id) as current_set,
               (SELECT MAX(game_number) FROM points WHERE match_id = m.id) as current_game
        FROM matches m
        ORDER BY m.created_at DESC
    ''').fetchall()
    
    conn.close()
    return jsonify([dict(match) for match in matches])

# Get match details
@app.route('/api/matches/<int:match_id>', methods=['GET'])
def get_match(match_id):
    conn = get_db()
    c = conn.cursor()
    
    match = c.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    if not match:
        conn.close()
        return jsonify({'error': 'Match not found'}), 404
    
    # Get games/sets data
    games = c.execute('''
        SELECT * FROM games 
        WHERE match_id = ? 
        ORDER BY set_number
    ''', (match_id,)).fetchall()
    
    # Get current point data
    current_points = c.execute('''
        SELECT * FROM points 
        WHERE match_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (match_id,)).fetchone()
    
    # Get all points for history
    all_points = c.execute('''
        SELECT * FROM points 
        WHERE match_id = ? 
        ORDER BY timestamp
    ''', (match_id,)).fetchall()
    
    conn.close()
    
    response = dict(match)
    response['games'] = [dict(game) for game in games]
    response['current_points'] = dict(current_points) if current_points else None
    response['points_history'] = [dict(point) for point in all_points]
    
    return jsonify(response)

# Update points
@app.route('/api/matches/<int:match_id>/point', methods=['POST'])
def add_point(match_id):
    data = request.json
    
    if 'team' not in data or data['team'] not in [1, 2]:
        return jsonify({'error': 'Invalid team specified'}), 400
    
    conn = get_db()
    c = conn.cursor()
    
    # Get current state
    match = c.execute('SELECT * FROM matches WHERE id = ?', (match_id,)).fetchone()
    if not match:
        conn.close()
        return jsonify({'error': 'Match not found'}), 404
    
    current_points = c.execute('''
        SELECT * FROM points 
        WHERE match_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (match_id,)).fetchone()
    
    if not current_points:
        conn.close()
        return jsonify({'error': 'No game found'}), 404
    
    # Update points
    new_team1_points = dict(current_points)['team1_points']
    new_team2_points = dict(current_points)['team2_points']
    
    if data['team'] == 1:
        new_team1_points += 1
    else:
        new_team2_points += 1
    
    # Insert new point record
    c.execute('''INSERT INTO points 
                 (match_id, set_number, game_number, team1_points, team2_points)
                 VALUES (?, ?, ?, ?, ?)''',
              (match_id, current_points['set_number'], 
               current_points['game_number'], 
               new_team1_points, new_team2_points))
    
    # Check if game is won and handle scoring
    handle_game_scoring(conn, c, match_id, match, current_points, 
                       new_team1_points, new_team2_points)
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

def handle_game_scoring(conn, c, match_id, match, current_points, team1_pts, team2_pts):
    """Handle game, set, and match logic"""
    # Padel scoring: 0, 15, 30, 40, game
    # Deuce at 40-40, advantage, etc.
    
    set_num = current_points['set_number']
    game_num = current_points['game_number']
    
    # Check if game is won (simplified logic - you can enhance this)
    if (team1_pts >= 4 and team1_pts - team2_pts >= 2) or \
       (team2_pts >= 4 and team2_pts - team1_pts >= 2):
        
        # Update game count
        current_game = c.execute('''
            SELECT * FROM games 
            WHERE match_id = ? AND set_number = ?
        ''', (match_id, set_num)).fetchone()
        
        team1_games = current_game['team1_games']
        team2_games = current_game['team2_games']
        
        if team1_pts > team2_pts:
            team1_games += 1
        else:
            team2_games += 1
        
        # Update games table
        c.execute('''
            UPDATE games 
            SET team1_games = ?, team2_games = ?
            WHERE match_id = ? AND set_number = ?
        ''', (team1_games, team2_games, match_id, set_num))
        
        # Check if set is won
        if (team1_games >= 6 and team1_games - team2_games >= 2) or \
           (team2_games >= 6 and team2_games - team1_games >= 2):
            
            # Update set score
            if team1_games > team2_games:
                new_team1_sets = match['team1_sets'] + 1
                new_team2_sets = match['team2_sets']
            else:
                new_team1_sets = match['team1_sets']
                new_team2_sets = match['team2_sets'] + 1
            
            c.execute('''
                UPDATE matches 
                SET team1_sets = ?, team2_sets = ?
                WHERE id = ?
            ''', (new_team1_sets, new_team2_sets, match_id))
            
            # Check if match is won (best of 3 sets typically)
            if new_team1_sets == 2 or new_team2_sets == 2:
                # Match won - could add completed flag here
                pass
            else:
                # Start new set
                new_set_num = set_num + 1
                c.execute('''
                    INSERT INTO games (match_id, set_number, team1_games, team2_games)
                    VALUES (?, ?, 0, 0)
                ''', (match_id, new_set_num))
        
        # Start new game (in current or next set)
        new_game_num = game_num + 1
        c.execute('''
            INSERT INTO points (match_id, set_number, game_number, team1_points, team2_points)
            VALUES (?, ?, ?, 0, 0)
        ''', (match_id, set_num, new_game_num))

# Undo last point
@app.route('/api/matches/<int:match_id>/undo', methods=['POST'])
def undo_point(match_id):
    conn = get_db()
    c = conn.cursor()
    
    # Get last point
    last_point = c.execute('''
        SELECT * FROM points 
        WHERE match_id = ? 
        ORDER BY timestamp DESC 
        LIMIT 1
    ''', (match_id,)).fetchone()
    
    if not last_point:
        conn.close()
        return jsonify({'error': 'No points to undo'}), 400
    
    # Delete the last point
    c.execute('DELETE FROM points WHERE id = ?', (last_point['id'],))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Delete a match
@app.route('/api/matches/<int:match_id>', methods=['DELETE'])
def delete_match(match_id):
    conn = get_db()
    c = conn.cursor()
    
    c.execute('DELETE FROM points WHERE match_id = ?', (match_id,))
    c.execute('DELETE FROM games WHERE match_id = ?', (match_id,))
    c.execute('DELETE FROM matches WHERE id = ?', (match_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    print("Starting Padel Score Tracker API...")
    print("Access the frontend at http://localhost:5000/frontend")
    print("API is running at http://localhost:5000/api/")
    app.run(debug=True, port=5000)