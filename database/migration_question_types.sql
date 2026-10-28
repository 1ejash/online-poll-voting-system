-- Question-type support for text answers and multi-select checkbox responses.
-- Safe to run repeatedly on MySQL-compatible databases.
ALTER TABLE polls ADD COLUMN IF NOT EXISTS poll_type VARCHAR(30) NOT NULL DEFAULT 'multiple_choice';

CREATE TABLE IF NOT EXISTS poll_answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    poll_id INT NOT NULL,
    selected_option_ids TEXT NULL,
    answer_text TEXT NULL,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_poll_answer (user_id, poll_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (poll_id) REFERENCES polls(id) ON DELETE CASCADE
);

CREATE INDEX idx_polls_status_expiry ON polls (status, expires_at);
CREATE INDEX idx_votes_poll ON votes (poll_id);
CREATE INDEX idx_options_poll ON poll_options (poll_id);
