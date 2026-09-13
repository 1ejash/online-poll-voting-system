# Online Poll and Voting System with Graphical Result Analysis

## Project Overview

This project is a web-based Online Poll and Voting System developed using Python Flask, MySQL, HTML, CSS, JavaScript, and Chart.js.

The system provides separate interfaces for users and administrators.

## Main Features

### User
- User registration
- Secure password hashing
- Separate user login
- View active polls
- Vote in a poll
- Duplicate vote prevention
- View voting results
- Bar chart and pie chart analysis
- Logout

### Administrator
- Separate admin login
- Admin dashboard
- Total users, polls, votes, and active poll statistics
- Create poll
- Edit poll
- Close/reopen poll
- Delete poll
- View poll results

## Technology Stack

- Frontend: HTML5, CSS3, JavaScript
- Backend: Python Flask
- Database: MySQL
- Graphs: Chart.js
- Password Security: Werkzeug password hashing

## Requirements

- Python 3.x
- XAMPP with MySQL
- MySQLdb dependencies supported by Flask-MySQLdb

## Installation

1. Start MySQL from XAMPP.
2. Open phpMyAdmin.
3. Create/import the database using:

   `database/database.sql`

4. Open PowerShell in the project folder.
5. Activate the virtual environment.
6. Install packages:

   `pip install -r requirements.txt`

7. Run:

   `python app.py`

8. Open:

   `http://127.0.0.1:5000/`

## Important Database Note

The SQL file creates the database tables. For an existing project database, keep your existing administrator account and existing poll data.

The admin account used during development is:

- Email: admin@gmail.com
- Password: admin123

If creating a completely new database, create the admin password hash using the application's password hashing mechanism instead of storing a plain password.

## Project Structure

online_poll_voting_system/
- app.py
- config.py
- requirements.txt
- README.md
- database/database.sql
- static/css/style.css
- static/js/main.js
- static/js/charts.js
- templates/

## Demo Flow

1. Open Home Page.
2. Demonstrate User Registration.
3. Login as User.
4. Open an active poll.
5. Submit a vote.
6. Demonstrate graphical results.
7. Try voting again to demonstrate duplicate-vote prevention.
8. Logout.
9. Login as Admin.
10. Demonstrate dashboard statistics.
11. Create a poll.
12. Edit the poll.
13. Close/reopen the poll.
14. View results.
15. Delete the test poll.

## Future Scope

- OTP/email verification
- Mobile application
- Real-time result updates
- Advanced analytics
- Multiple administrator roles
- Cloud deployment
