// API Base URL - pointing to local Flask server
const API_BASE_URL = 'http://localhost:5000/api';

// DOM Elements
const createMatchBtn = document.getElementById('create-match-btn');
const team1PointBtn = document.getElementById('team1-point');
const team2PointBtn = document.getElementById('team2-point');
const undoBtn = document.getElementById('undo-btn');
const endMatchBtn = document.getElementById('end-match-btn');

// State
let currentMatchId = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadMatches();
    setupEventListeners();
});

function setupEventListeners() {
    createMatchBtn.addEventListener('click', createMatch);
    team1PointBtn.addEventListener('click', () => addPoint(1));
    team2PointBtn.addEventListener('click', () => addPoint(2));
    undoBtn.addEventListener('click', undoLastPoint);
    endMatchBtn.addEventListener('click', endCurrentMatch);
}

// Create a new match
async function createMatch() {
    const team1Player1 = document.getElementById('team1-player1').value.trim();
    const team1Player2 = document.getElementById('team1-player2').value.trim();
    const team2Player1 = document.getElementById('team2-player1').value.trim();
    const team2Player2 = document.getElementById('team2-player2').value.trim();

    if (!team1Player1 || !team1Player2 || !team2Player1 || !team2Player2) {
        alert('Please fill in all player names');
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/matches`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                team1_player1: team1Player1,
                team1_player2: team1Player2,
                team2_player1: team2Player2,
                team2_player2: team2Player2
            })
        });

        if (response.ok) {
            const match = await response.json();
            currentMatchId = match.id;
            
            // Clear form
            document.getElementById('team1-player1').value = '';
            document.getElementById('team1-player2').value = '';
            document.getElementById('team2-player1').value = '';
            document.getElementById('team2-player2').value = '';
            
            // Load the new match
            loadCurrentMatch();
            loadMatches();
            
            // Show score controls
            document.getElementById('score-controls').style.display = 'block';
        } else {
            const error = await response.json();
            alert(`Error creating match: ${error.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to create match. Please check if the server is running.');
    }
}

// Load current match
async function loadCurrentMatch() {
    if (!currentMatchId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/matches/${currentMatchId}`);
        if (response.ok) {
            const match = await response.json();
            displayCurrentMatch(match);
        }
    } catch (error) {
        console.error('Error loading match:', error);
    }
}

// Display current match
function displayCurrentMatch(match) {
    const currentMatchDiv = document.getElementById('current-match');
    
    // Convert points to padel scoring (0, 15, 30, 40, AD)
    function getPadelScore(points) {
        const scores = ['0', '15', '30', '40', 'AD'];
        return points < 5 ? scores[points] : 'AD';
    }
    
    const team1Points = match.current_points?.team1_points || 0;
    const team2Points = match.current_points?.team2_points || 0;
    
    currentMatchDiv.innerHTML = `
        <div class="score-display">
            <h3>Set ${match.current_points?.set_number || 1} - Game ${match.current_points?.game_number || 1}</h3>
            
            <div class="teams-container">
                <div class="team-score">
                    <div class="team-name">Team 1</div>
                    <div class="players">${match.team1_player1} & ${match.team1_player2}</div>
                    <div class="set-score">${match.team1_sets}</div>
                    <div class="current-points">
                        <div class="point-label">Current Points:</div>
                        <div class="point-score">${getPadelScore(team1Points)}</div>
                    </div>
                </div>
                
                <div style="font-size: 2rem; margin: 20px 0;">VS</div>
                
                <div class="team-score">
                    <div class="team-name">Team 2</div>
                    <div class="players">${match.team2_player1} & ${match.team2_player2}</div>
                    <div class="set-score">${match.team2_sets}</div>
                    <div class="current-points">
                        <div class="point-label">Current Points:</div>
                        <div class="point-score">${getPadelScore(team2Points)}</div>
                    </div>
                </div>
            </div>
            
            <div class="match-info">
                <p>Games in current set: 
                    ${match.games?.find(g => g.set_number === match.current_points?.set_number)?.team1_games || 0} - 
                    ${match.games?.find(g => g.set_number === match.current_points?.set_number)?.team2_games || 0}
                </p>
            </div>
        </div>
    `;
}

// Add a point
async function addPoint(team) {
    if (!currentMatchId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/matches/${currentMatchId}/point`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ team: team })
        });

        if (response.ok) {
            loadCurrentMatch();
            loadMatches(); // Update history
        } else {
            const error = await response.json();
            alert(`Error adding point: ${error.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// Undo last point
async function undoLastPoint() {
    if (!currentMatchId) return;

    try {
        const response = await fetch(`${API_BASE_URL}/matches/${currentMatchId}/undo`, {
            method: 'POST'
        });

        if (response.ok) {
            loadCurrentMatch();
            loadMatches();
        } else {
            const error = await response.json();
            alert(`Error undoing point: ${error.error}`);
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

// End current match
async function endCurrentMatch() {
    if (!currentMatchId) return;

    if (confirm('Are you sure you want to end this match?')) {
        try {
            const response = await fetch(`${API_BASE_URL}/matches/${currentMatchId}`, {
                method: 'DELETE'
            });

            if (response.ok) {
                currentMatchId = null;
                document.getElementById('current-match').innerHTML = `
                    <div class="no-match">
                        <p>No active match. Create one to get started!</p>
                    </div>
                `;
                document.getElementById('score-controls').style.display = 'none';
                loadMatches();
            }
        } catch (error) {
            console.error('Error:', error);
        }
    }
}

// Load all matches
async function loadMatches() {
    try {
        const response = await fetch(`${API_BASE_URL}/matches`);
        if (response.ok) {
            const matches = await response.json();
            displayMatches(matches);
        }
    } catch (error) {
        console.error('Error loading matches:', error);
        document.getElementById('match-history').innerHTML = `
            <p class="loading">Error loading matches. Make sure the server is running at ${API_BASE_URL}</p>
        `;
    }
}

// Display matches in history
function displayMatches(matches) {
    const historyDiv = document.getElementById('match-history');
    
    if (matches.length === 0) {
        historyDiv.innerHTML = '<p class="loading">No matches yet. Create your first match!</p>';
        return;
    }
    
    historyDiv.innerHTML = matches.map(match => {
        const date = new Date(match.created_at);
        const dateStr = date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
        
        return `
            <div class="match-item" data-id="${match.id}">
                <div class="match-teams">
                    <span>${match.team1_player1} & ${match.team1_player2}</span>
                    <span>${match.team1_sets} - ${match.team2_sets}</span>
                    <span>${match.team2_player1} & ${match.team2_player2}</span>
                </div>
                <div class="match-result">
                    Sets: ${match.team1_sets} - ${match.team2_sets} | 
                    Current Set: ${match.current_set || 1} | 
                    Current Game: ${match.current_game || 1}
                </div>
                <div class="match-date">${dateStr}</div>
            </div>
        `;
    }).join('');
    
    // Add click event to load match when clicked
    document.querySelectorAll('.match-item').forEach(item => {
        item.addEventListener('click', () => {
            const matchId = parseInt(item.dataset.id);
            currentMatchId = matchId;
            loadCurrentMatch();
            document.getElementById('score-controls').style.display = 'block';
        });
    });
}

// Auto-refresh current match every 2 seconds
setInterval(() => {
    if (currentMatchId) {
        loadCurrentMatch();
    }
}, 2000);