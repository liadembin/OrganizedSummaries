from typing import Any
from dotenv import load_dotenv
import os
from typing import Optional
import sys

# import logging
from typing import List, Dict

# from datetime import datetime
from mysql.connector import Error
from unittest.mock import Mock, patch, MagicMock
import pytest
import mysql.connector
from mysql.connector import MySQLConnection, Error
import datetime
from dataclasses import dataclass, field
from typing import Tuple
import hashlib
import uuid
import base64
from mysql.connector.pooling import PooledMySQLConnection
import re
import pickle
import datetime
from mysql.connector import Error, MySQLConnection, pooling
from mysql.connector.pooling import PooledMySQLConnection
from dataclasses import dataclass, field


@dataclass
class User:
    id: int
    username: str
    hashedPass: str
    salt: str
    isPublic: bool
    createTime: datetime.datetime = None

    def __post_init__(self):
        if self.createTime is None:
            self.createTime = datetime.datetime.now()


# {"username": "u1", "position": 1, "content": "hello", "type": "insert"}
@dataclass
class Summary:
    id: int
    ownerId: int
    shareLink: str
    path_to_summary: str
    font: str
    createTime: Optional[datetime.datetime] = None
    updateTime: Optional[datetime.datetime] = None
    content: str = ""


@dataclass(eq=True, frozen=False)
class Node:
    id: int
    name: str
    type: str
    children: List["Node"] = field(default_factory=list, compare=False, hash=False)

    def __hash__(self):
        return hash((self.id, self.name, self.type))


class DbManager:
    def __init__(self):
        self.connection: Optional[MySQLConnection | PooledMySQLConnection] = None
        self.cursor: Any = None
        self.id_per_sock: Dict[Any, int] = {}

    def get_is_sock_logged(self, sock: Any) -> bool:
        return sock in self.id_per_sock

    def get_id_per_sock(self, sock: Any) -> int:
        return self.id_per_sock.get(sock, -1)

    def connect_to_db(self, db_config: Dict[str, Any]) -> None:
        """Connect to MySQL database."""
        try:
            self.connection = mysql.connector.connect(**db_config)
            self.cursor = self.connection.cursor(dictionary=True)
            print("Connected to database")
        except Error as e:
            print(f"Error connecting to database: {e}")

    def get_id_by_username(self, username: str) -> int:
        query = "SELECT id FROM User WHERE username = %s"
        self.cursor.execute(query, (username,))
        result = self.cursor.fetchone()
        return result["id"] if result else -1

    def insert_user(self, username: str, password_hash: str, salt: bytes) -> bool:
        """Insert a new user into the database."""
        try:
            query = """
                INSERT INTO user (username, hashedPass, salt, isPublic)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(
                query, (username, password_hash, base64.b64encode(salt).decode(), 0)
            )
            self.connection.commit()
            print("Created user")
            return True
        except Error as e:
            print(f"Error inserting user: {e}")
            return False

    def share_summary(
        self,
        summary_id: int,
        owner_id: int,
        user_to_share_with_id: int,
        permission_type: str,
    ) -> bool:
        """Verify if the user owns the summary, then share it with another user."""
        try:
            # 1. Verify ownership: Check if the user is the owner of the summary
            query = """
                SELECT ownerId FROM summary WHERE id = %s
            """
            self.cursor.execute(query, (summary_id,))
            result = self.cursor.fetchone()

            # If no result is found or the owner doesn't match
            if result is None or result["ownerId"] != owner_id:
                print("User does not own this summary.")
                return False

            # 2. Share the summary: Insert permission record to share with another user
            query = """
                INSERT INTO permission (summaryId, userId, permissionType)
                VALUES (%s, %s, %s)
            """
            self.cursor.execute(
                query, (summary_id, user_to_share_with_id, permission_type)
            )
            self.connection.commit()

            print(
                f"Summary {summary_id} shared with user {user_to_share_with_id} with {permission_type} permission."
            )
            return True
        except Error as e:
            print(f"Error sharing summary: {e}")
            return False

    def get_user(self, username: str) -> Optional[User]:
        """Get user by username."""
        try:
            query = "SELECT * FROM User WHERE username = %s"
            self.cursor.execute(query, (username,))
            user = self.cursor.fetchone()
            if user:
                return User(**user)
            return None
        except Error as e:
            print(f"Error getting user: {e}")
            return None

    def get_salt(self, username: str) -> Optional[bytes]:
        """Get salt for a user."""
        try:
            query = "SELECT salt FROM User WHERE username = %s"
            self.cursor.execute(query, (username,))
            result = self.cursor.fetchone()
            return base64.b64decode(result["salt"]) if result else b""
        except Error as e:
            print(f"Error fetching salt: {e}")
            return b""

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        try:
            query = "SELECT * FROM User WHERE id = %s"
            self.cursor.execute(query, (user_id,))
            user_data = self.cursor.fetchone()
            if user_data:
                return User(**user_data)
            return None
        except Error as e:
            print(f"Error getting user by ID: {e}")
            return None

    def authenticate_user(self, username: str, password_hash: str) -> Optional[User]:
        """Authenticate user by username and password hash."""
        try:
            query = "SELECT * FROM User WHERE username = %s AND hashedPass = %s"
            self.cursor.execute(
                query,
                (
                    username,
                    password_hash,
                ),
            )
            user_data = self.cursor.fetchone()
            print("User data: ", user_data)
            if user_data:
                return User(**user_data)
            return None
        except Error as e:
            print(f"Error authenticating user: {e}")
            return None

    def update_user_password(self, username: str, new_password_hash: str) -> bool:
        """Update user password."""
        try:
            query = "UPDATE User SET hashedPass = %s WHERE username = %s"
            self.cursor.execute(
                query,
                (
                    new_password_hash,
                    username,
                ),
            )
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating password: {e}")
            return False

    def _extract_links(self, content: str) -> Tuple[str, Dict[str, str]]:
        """
        Extract links from content in the format "###link {name}" ending with a newline.
        Returns processed content and dictionary of {link_title: link_id}.
        """
        # Pattern to match ###link {name} ending with a newline
        pattern = r"###link\s+([^\n]+)\n"
        links = {}

        # Find all links
        matches = re.findall(pattern, content)
        print("matches for links: ", matches)
        # Process each link
        for match in matches:
            link_title = match.strip()
            # Get the summary ID based on the title
            summary_id = self._get_summary_id_by_title(link_title)
            print(f"sid: {summary_id} for link: {link_title}")
            if summary_id:
                links[link_title] = summary_id

        return content, links

    def _get_summary_id_by_title(self, title: str) -> Optional[int]:
        """Get summary ID by title."""
        try:
            query = "SELECT id FROM Summary WHERE shareLink = %s"
            self.cursor.execute(query, (title,))
            result = self.cursor.fetchone()
            return result["id"] if result else None
        except Error as e:
            print(f"Error fetching summary ID by title: {e}")
            return None

    def _save_links(self, source_id: int, links: Dict[str, str]) -> None:
        """Save links between summaries in the database."""
        try:
            # Create links table if it doesn't exist
            # create_table_query = """
            #     CREATE TABLE IF NOT EXISTS links (
            #         id INT AUTO_INCREMENT PRIMARY KEY,
            #         source_summary_id INT NOT NULL,
            #         target_summary_id INT NOT NULL,
            #         link_text VARCHAR(255),
            #         FOREIGN KEY (source_summary_id) REFERENCES Summary(id) ON DELETE CASCADE,
            #         FOREIGN KEY (target_summary_id) REFERENCES Summary(id) ON DELETE CASCADE
            #     )
            # """
            # self.cursor.execute(create_table_query)

            # Insert links
            for link_text, target_id in links.items():
                query = """
                    INSERT INTO links (source_summary_id, target_summary_id, link_text)
                    VALUES (%s, %s, %s)
                """
                self.cursor.execute(query, (source_id, target_id, link_text))

            self.connection.commit()
            print(f"Saved {len(links)} links for summary {source_id}")
        except Error as e:
            print(f"Error saving links: {e}")

    def insert_summary(
        self, title: str, content: str, created_by: int, font: str
    ) -> int:
        """Insert new summary and save to disk, return its ID."""
        try:
            # Get the current maximum ID
            self.cursor.execute("SELECT MAX(id) FROM Summary")
            max_id_before = self.cursor.fetchone()["MAX(id)"] or 0

            # Create directory for user if it doesn't exist
            user_dir = os.path.join("data", str(created_by))
            os.makedirs(user_dir, exist_ok=True)

            # Generate unique filename
            base_filename = f"{title.replace(' ', '_')}.md"
            filepath = os.path.join(user_dir, base_filename)

            # Check and modify filename if it already exists
            counter = 1
            while os.path.exists(filepath):
                filename = f"{title.replace(' ', '_')}({counter}).md"
                filepath = os.path.join(user_dir, filename)
                counter += 1

            # Process content to extract links
            processed_content, links = self._extract_links(content)

            # Write content to file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(processed_content)

            # Insert summary record
            query = """
                INSERT INTO Summary (ownerId, shareLink, path_to_summary, font)
                VALUES (%s, %s, %s, %s)
            """
            self.cursor.execute(query, (created_by, title, filepath, font))
            self.connection.commit()

            # Get the maximum ID after insertion
            self.cursor.execute("SELECT MAX(id) FROM Summary")
            max_id_after = self.cursor.fetchone()["MAX(id)"] or 0

            new_summary_id = max_id_after if max_id_after > max_id_before else -1

            # Save links if insertion was successful
            if new_summary_id > 0 and links:
                self._save_links(new_summary_id, links)

            return new_summary_id

        except (Error, IOError) as e:
            print(f"Error inserting summary: {e}")
            return -1

    def save_summary(self, sid: int, content: str) -> bool:
        """Save updated summary content and process links."""
        try:
            query = "SELECT path_to_summary FROM Summary WHERE id = %s"
            self.cursor.execute(query, (sid,))
            result = self.cursor.fetchone()
            if not result:
                return False

            filepath = result["path_to_summary"]

            # Process content to extract and update links
            processed_content, links = self._extract_links(content)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(processed_content)

            # Update links for this summary
            self._update_links(sid, links)

            return True
        except (Error, IOError) as e:
            print(f"Error saving summary: {e}")
            return False

    def _update_links(self, source_id: int, links: Dict[str, str]) -> None:
        """Update links between summaries in the database."""
        try:
            # First delete all existing links from this source
            delete_query = """
                DELETE FROM links WHERE source_summary_id = %s
            """
            self.cursor.execute(delete_query, (source_id,))

            # Then insert new links
            if links:
                self._save_links(source_id, links)

            self.connection.commit()
        except Error as e:
            print(f"Error updating links: {e}")

    def _delete_links(self, summary_id: str) -> None:
        """Delete all links associated with a summary."""
        try:
            # Delete links where this summary is the source
            query1 = "DELETE FROM links WHERE source_summary_id = %s"
            self.cursor.execute(query1, (summary_id,))

            # Delete links where this summary is the target
            query2 = "DELETE FROM links WHERE target_summary_id = %s"
            self.cursor.execute(query2, (summary_id,))

            self.connection.commit()
        except Error as e:
            print(f"Error deleting links: {e}")

    def get_summary(self, summary_id: str) -> Optional[Summary]:
        """Get summary by ID, including file contents."""
        try:
            query = "SELECT * FROM Summary WHERE id = %s"
            self.cursor.execute(query, (summary_id,))
            summary_data = self.cursor.fetchone()

            if summary_data:
                # Read file contents if path exists
                if summary_data["path_to_summary"] and os.path.exists(
                    summary_data["path_to_summary"]
                ):
                    with open(
                        summary_data["path_to_summary"], "r", encoding="utf-8"
                    ) as f:
                        summary_data["content"] = f.read()
                return Summary(**summary_data)

            return None

        except (Error, IOError) as e:
            print(f"Error getting summary: {e}")
            return None

    def get_summary_by_link(self, link: str) -> Optional[Summary]:
        """Get summary by share link."""
        try:
            query = "SELECT * FROM Summary WHERE LOWER(shareLink) = LOWER(%s)"
            self.cursor.execute(query, (link,))
            summary_data = self.cursor.fetchone()

            if summary_data:
                # Read file contents if path exists
                if summary_data["path_to_summary"] and os.path.exists(
                    summary_data["path_to_summary"]
                ):
                    with open(
                        summary_data["path_to_summary"], "r", encoding="utf-8"
                    ) as f:
                        summary_data["content"] = f.read()
                return Summary(**summary_data)

            return None

        except (Error, IOError) as e:
            print(f"Error getting summary: {e}")
            return None

    def update_summary(self, summary_id: str, content: str, font=None) -> bool:
        """Update a summary's shareLink and optionally its content."""
        try:
            # Fetch current summary to get existing path
            query = "SELECT path_to_summary FROM Summary WHERE id = %s"
            self.cursor.execute(query, (summary_id,))
            result = self.cursor.fetchone()

            if not result:
                return False

            filepath = result["path_to_summary"]

            # Update file content if provided
            if content and filepath:
                # Process content to extract and update links
                processed_content, links = self._extract_links(content)

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(processed_content)

                # Update links for this summary
                self._update_links(int(summary_id), links)

            # Update database record
            update_query = "UPDATE Summary SET font = %s WHERE id = %s"
            self.cursor.execute(update_query, (font, summary_id))
            self.connection.commit()

            return True

        except (Error, IOError) as e:
            print(f"Error updating summary: {e}")
            return False

    def delete_summary(self, summary_id: str) -> bool:
        """Delete a summary from database and file system."""
        try:
            # Fetch filepath before deletion
            query = "SELECT path_to_summary FROM Summary WHERE id = %s"
            self.cursor.execute(query, (summary_id,))
            result = self.cursor.fetchone()

            # Delete links associated with this summary
            self._delete_links(summary_id)

            # Delete from database
            delete_query = "DELETE FROM Summary WHERE id = %s"
            self.cursor.execute(delete_query, (summary_id,))
            self.connection.commit()

            # Delete file if it exists
            if (
                result
                and result["path_to_summary"]
                and os.path.exists(result["path_to_summary"])
            ):
                os.remove(result["path_to_summary"])

            return True

        except (Error, IOError) as e:
            print(f"Error deleting summary: {e}")
            return False

    def insert_event(self, user_id: int, title: str, datetime_str: str) -> bool:
        """Insert a new event for a user with datetime."""
        try:
            query = """
            INSERT INTO Event (userId, event_title, event_date)
            VALUES (%s, %s, %s)
            """
            self.cursor.execute(query, (user_id, title, datetime_str))
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error inserting event: {e}")
            return False

    def get_events(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all events for a user."""
        try:
            query = "SELECT * FROM Event WHERE userid = %s ORDER BY event_date ASC"
            self.cursor.execute(query, (user_id,))
            events = self.cursor.fetchall()
            return events
        except Error as e:
            print(f"Error fetching events: {e}")
            return []

    def update_event(self, event_id: int, new_title: str, new_date: str) -> bool:
        """Update an existing event."""
        try:
            query = "UPDATE Event SET event_title = %s, event_date = %s WHERE id = %s"
            self.cursor.execute(
                query,
                (
                    new_title,
                    new_date,
                    event_id,
                ),
            )
            self.connection.commit()
            return True
        except Error as e:
            print(f"Error updating event: {e}")
            return False

    def delete_event(self, event_id: str, user_id: int) -> bool:
        """Delete an event if it belongs to the specified user."""
        try:
            # First verify the event belongs to this user
            check_query = """
            SELECT id FROM Event
            WHERE id = %s AND userId = %s
            """
            self.cursor.execute(check_query, (event_id, user_id))
            if not self.cursor.fetchone():
                print("Event doesn't exist or doesn't belong to this user")
                return False

            # Now delete the event
            delete_query = """
            DELETE FROM Event
            WHERE id = %s AND userId = %s
            """
            self.cursor.execute(delete_query, (event_id, user_id))
            self.connection.commit()
            print("Removed event:  ", event_id, " from user: ", user_id)
            return True
        except Error as e:
            print(f"Error deleting event: {e}")
            return False

    def close_connection(self) -> None:
        """Close the database connection."""
        if self.connection:
            self.cursor.close()
            self.connection.close()

    def get_summary_share_link(self, id: int) -> str:
        """Get the share link for a summary."""
        try:
            query = "SELECT shareLink FROM Summary WHERE id = %s"
            self.cursor.execute(query, (id,))
            result = self.cursor.fetchone()
            return result["shareLink"] if result else ""
        except Error as e:
            print(f"Error fetching summary share link: {e}")
            return ""

    def update_permission(self, summary_id: int, user_id: int, new_perm: str) -> bool:
        """
        Update permission for a specific user and summary.

        :param summary_id: The ID of the summary whose permission is being updated.
        :param user_id: The ID of the user whose permission is being updated.
        :param new_perm: The new permission to set ('view', 'edit', 'comment').
        :return: True if the update was successful, False otherwise.
        """
        try:
            query = """
                UPDATE permission
                SET permissionType = %s
                WHERE summaryId = %s AND userId = %s
            """
            self.cursor.execute(query, (new_perm, summary_id, user_id))
            self.connection.commit()
            return (
                self.cursor.rowcount > 0
            )  # Return True if at least one row was updated
        except Error as e:
            print(f"Error updating permission: {e}")
            return False

    def get_summary_times(self, id: int) -> List[datetime.datetime]:
        """Get creation and update times of a summary."""
        try:
            query = "SELECT createTime, updateTime FROM Summary WHERE id = %s"
            self.cursor.execute(query, (id,))
            result = self.cursor.fetchone()
            return [result["createTime"], result["updateTime"]] if result else []
        except Error as e:
            print(f"Error fetching summary times: {e}")
            return []

    def get_all_by_user(self, user_id: int) -> List[Summary]:
        """Get all summaries created by a user."""
        try:
            query = "SELECT * FROM Summary WHERE ownerId = %s"
            self.cursor.execute(query, (user_id,))
            summaries = self.cursor.fetchall()
            return [Summary(**summar) for summar in summaries]
        except Error as e:
            print(f"Error fetching all summaries by user: {e}")
            return []

    def get_all_user_can_access(self, user_id: int) -> List[Summary]:
        """Get all summaries the user can access, including owned and permitted ones."""
        try:
            query = """
                SELECT DISTINCT s.*
                FROM summary s
                LEFT JOIN permission p ON s.id = p.summaryId AND p.userId = %s
                WHERE s.ownerId = %s OR p.userId = %s
            """
            self.cursor.execute(query, (user_id, user_id, user_id))
            summaries = self.cursor.fetchall()
            return [Summary(**su) for su in summaries]
        except Error as e:
            print(f"Error fetching summaries user can access: {e}")
            return []

    def get_graph(self, summary_id: int) -> List[Node]:
        """
        Build a graph representation for a summary and its connections.
        Returns a list of Node objects representing the graph structure.
        """
        try:
            # Get the current summary
            query = "SELECT id, shareLink FROM Summary WHERE id = %s"
            self.cursor.execute(query, (summary_id,))
            current_summary = self.cursor.fetchone()

            if not current_summary:
                return []

            # Initialize the graph with the current summary as root
            root_node = Node(
                id=current_summary["id"],
                name=current_summary["shareLink"],
                type="summary",
                children=[],
            )

            # Find parent summaries (summaries that link to this one)
            parent_query = """
                SELECT s.id, s.shareLink
                FROM Summary s
                JOIN links l ON s.id = l.source_summary_id
                WHERE l.target_summary_id = %s
            """
            self.cursor.execute(parent_query, (summary_id,))
            parents = self.cursor.fetchall()

            # Find child summaries (summaries that this one links to)
            child_query = """
                SELECT s.id, s.shareLink
                FROM Summary s
                JOIN links l ON s.id = l.target_summary_id
                WHERE l.source_summary_id = %s
            """
            self.cursor.execute(child_query, (summary_id,))
            children = self.cursor.fetchall()

            # Add children to the root node
            for child in children:
                child_node = Node(
                    id=child["id"], name=child["shareLink"], type="child", children=[]
                )
                root_node.children.append(child_node)

            # Create parent nodes
            parent_nodes = []
            for parent in parents:
                parent_node = Node(
                    id=parent["id"],
                    name=parent["shareLink"],
                    type="parent",
                    children=[root_node],  # The current node is a child of each parent
                )
                parent_nodes.append(parent_node)

            # Combine into a single result
            result = [root_node]
            result.extend(parent_nodes)

            # Optionally save the graph structure using pickle
            graph_dir = "data/graphs"
            os.makedirs(graph_dir, exist_ok=True)
            graph_path = os.path.join(graph_dir, f"graph_{summary_id}.pkl")

            with open(graph_path, "wb") as f:
                pickle.dump(result, f)

            return result

        except (Error, IOError) as e:
            print(f"Error generating graph: {e}")
            return []


# Mock classes to match the expected structures


@pytest.fixture
def db_manager():
    manager = DbManager()
    manager.connection = MagicMock()
    manager.cursor = MagicMock()
    return manager


def test_connect_to_db_success(db_manager):
    with patch("mysql.connector.connect") as mock_connect:
        db_manager.connect_to_db("mock_url")
        mock_connect.assert_called_once_with(url="mock_url")


def test_connect_to_db_failure(db_manager):
    with patch("mysql.connector.connect", side_effect=Error("Connection failed")):
        with pytest.raises(Exception):
            db_manager.connect_to_db("mock_url")


class TestUserOperations:
    def test_insert_user_success(self, db_manager):
        db_manager.cursor.execute.return_value = None
        db_manager.connection.commit.return_value = None

        result = db_manager.insert_user("testuser", "hashed_pass", "salt")
        assert result is True
        db_manager.cursor.execute.assert_called_once()
        db_manager.connection.commit.assert_called_once()

    def test_insert_user_failure(self, db_manager):
        db_manager.cursor.execute.side_effect = Error("Insert failed")

        result = db_manager.insert_user("testuser", "hashed_pass", "salt")
        assert result is False

    def test_get_user_success(self, db_manager):
        mock_user = {
            "id": "123",
            "username": "testuser",
            "hashedPass": "hash",
            "salt": "salt",
            "isPublic": False,
        }
        db_manager.cursor.fetchone.return_value = mock_user

        result = db_manager.get_user("testuser")
        assert isinstance(result, User)
        assert result.username == "testuser"

    def test_get_user_not_found(self, db_manager):
        db_manager.cursor.fetchone.return_value = None

        result = db_manager.get_user("nonexistent")
        assert result is None

    def test_authenticate_user_success(self, db_manager):
        mock_user = {
            "id": "123",
            "username": "testuser",
            "hashedPass": "hash",
            "salt": "salt",
            "isPublic": False,
        }
        db_manager.cursor.fetchone.return_value = mock_user

        result = db_manager.authenticate_user("testuser", "hash")
        assert isinstance(result, User)
        assert result.username == "testuser"

    def test_authenticate_user_failure(self, db_manager):
        db_manager.cursor.fetchone.return_value = None

        result = db_manager.authenticate_user("testuser", "wrong_hash")
        assert result is None


class TestSummaryOperations:
    def test_insert_summary_success(self, db_manager):
        db_manager.cursor.execute.return_value = None
        db_manager.connection.commit.return_value = None

        result = db_manager.insert_summary("Test Title", "content", 1, ["tag1", "tag2"])
        assert isinstance(result, int)
        assert result != -1

    def test_insert_summary_failure(self, db_manager):
        db_manager.cursor.execute.side_effect = Error("Insert failed")

        result = db_manager.insert_summary("Test Title", "content", 1, ["tag1"])
        assert result == -1

    def test_get_summary_success(self, db_manager):
        mock_summary = {
            "id": "123",
            "ownerId": 1,
            "shareLink": "link",
            "path_to_summary": "path",
        }
        db_manager.cursor.fetchone.return_value = mock_summary

        result = db_manager.get_summary("123")
        assert isinstance(result, Summary)
        assert result.id == "123"

    def test_get_summary_not_found(self, db_manager):
        db_manager.cursor.fetchone.return_value = None

        result = db_manager.get_summary("nonexistent")
        assert result is None


class TestEventOperations:
    def test_insert_event_success(self, db_manager):
        db_manager.cursor.execute.return_value = None
        db_manager.connection.commit.return_value = None

        result = db_manager.insert_event(1, "Test Event", "2025-01-22")
        assert isinstance(result, str)
        assert result != -1

    def test_insert_event_failure(self, db_manager):
        db_manager.cursor.execute.side_effect = Error("Insert failed")

        result = db_manager.insert_event(1, "Test Event", "2025-01-22")
        assert result == -1

    def test_get_events_success(self, db_manager):
        mock_events = [
            {
                "id": "1",
                "userid": 1,
                "event_title": "Event 1",
                "event_date": "2025-01-22",
            },
            {
                "id": "2",
                "userid": 1,
                "event_title": "Event 2",
                "event_date": "2025-01-23",
            },
        ]
        db_manager.cursor.fetchall.return_value = mock_events

        result = db_manager.get_events(1)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["event_title"] == "Event 1"

    def test_get_events_empty(self, db_manager):
        db_manager.cursor.fetchall.return_value = []

        result = db_manager.get_events(1)
        assert isinstance(result, list)
        assert len(result) == 0


def test_close_connection(db_manager):
    db_manager.close_connection()
    db_manager.cursor.close.assert_called_once()
    db_manager.connection.close.assert_called_once()


class TestPermissionOperations:
    def test_update_permission_success(self, db_manager):
        db_manager.cursor.execute.return_value = None
        db_manager.connection.commit.return_value = None

        result = db_manager.update_permission(1, 1, "public")
        assert result is True

    def test_update_permission_failure(self, db_manager):
        db_manager.cursor.execute.side_effect = Error("Update failed")

        result = db_manager.update_permission(1, 3, "public")
        assert result is False

    def test_get_all_user_can_access(self, db_manager):
        mock_summaries = [
            {"id": "1", "ownerId": 1, "shareLink": "link1", "path_to_summary": "path1"},
            {"id": "2", "ownerId": 2, "shareLink": "link2", "path_to_summary": "path2"},
        ]
        db_manager.cursor.fetchall.return_value = mock_summaries

        result = db_manager.get_all_user_can_access(1)
        assert isinstance(result, list)
        assert len(result) == 2
        assert all(isinstance(s, Summary) for s in result)


# Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#     handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("app.log")],
# )
# logger = logging.getLogger(__name__)
#
#
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password with salt."""
    if not salt:
        salt = uuid.uuid4().hex
    hashed = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000
    ).hex()
    return hashed, salt


def demo_user_operations(db: DbManager) -> Optional[str]:
    """Demonstrate user operations."""
    try:
        # Create a new user
        password, salt = hash_password("secure_password123")
        username = f"testuser_{uuid.uuid4().hex[:8]}"
        user_id = db.insert_user(username, password, b"AAAA")

        if not user_id:
            print("Failed to create user")
            return None

        print(f"Created user with ID: {user_id}")

        # Authenticate user
        auth_user = db.authenticate_user(username, password)
        if auth_user:
            print(f"Successfully authenticated user: {auth_user.username}")

        # Update password
        new_password, new_salt = hash_password("new_secure_password456")
        if db.update_user_password(username, new_password):
            print("Successfully updated password")

        return user_id
    except Exception as e:
        print(f"Error in user operations: {e}")
        return None


def demo_summary_operations(db: DbManager, user_id: str) -> Optional[str]:
    """Demonstrate summary operations."""
    try:
        # Create a summary
        title = "Test Summary"
        content = "This is a test summary content."
        tags = ["test", "demo", "example"]
        print("Inserting summary.")
        summary_id = db.insert_summary(title, content, user_id, tags)
        if summary_id == -1:
            print("Failed to create summary")
            return None

        print(f"Created summary with ID: {summary_id}")

        # Update summary
        share_link = f"{summary_id}"
        path = f"/summaries/{summary_id}.md"
        if db.update_summary(summary_id, share_link, path):
            print("Successfully updated summary")

        # Update permissions
        if db.update_permission(summary_id, int(user_id), "public"):
            print("Successfully updated summary permissions")

        # Get summary times
        times = db.get_summary_times(summary_id)
        if times:
            print(f"Summary created at: {times[0]}, last updated at: {times[1]}")

        return summary_id
    except Exception as e:
        print(f"Error in summary operations: {e}")
        return None


def demo_event_operations(db: DbManager, user_id: str) -> Optional[str]:
    """Demonstrate event operations."""
    try:
        # Create an event
        event_title = "Test Event"
        event_date = datetime.datetime.now().strftime("%Y-%m-%d")

        event_id = db.insert_event(user_id, event_title, event_date)
        if event_id == -1:
            print("Failed to create event")
            return None

        print(f"Created event with ID: {event_id}")

        # Get user's events
        events = db.get_events(user_id)
        print(f"Found {len(events)} events for user")

        # Update event
        new_title = "Updated Test Event"
        new_date = (
            datetime.datetime.now()
            .replace(day=datetime.datetime.now().day + 1)
            .strftime("%Y-%m-%d")
        )
        if db.update_event(event_id, new_title, new_date):
            print("Successfully updated event")

        return event_id
    except Exception as e:
        print(f"Error in event operations: {e}")
        return None


def main():
    load_dotenv()  # Load environment variables from .env file
    try:
        db = DbManager()
        db.connect_to_db(
            {
                "host": "localhost",
                "user": "root",
                "password": (
                    os.getenv("DB_PASSWORD")
                    if os.getenv("DB_PASSWORD")
                    else "liad8888"
                    if os.getenv("DB_PASSWORD")
                    else "liad8888"
                ),
                "database": "finalprojtest",
                "port": 3306,
            }
        )
        # Demonstrate user operations
        user_id = demo_user_operations(db)
        print("Uid: ", user_id)
        if not user_id:
            print("User operations failed")
            return

        # Demonstrate summary operations
        summary_id = demo_summary_operations(db, user_id)
        if not summary_id:
            print("Summary operations failed")
            return

        # Demonstrate event operations
        event_id = demo_event_operations(db, user_id)
        if not event_id:
            print("Event operations failed")
            return

        # Demonstrate fetching all accessible summaries
        summaries = db.get_all_user_can_access(user_id)
        print(f"User can access {len(summaries)} summaries")

        # Clean up by deleting created resources
        if db.delete_summary(summary_id):
            print("Successfully deleted summary")
        if db.delete_event(event_id):
            print("Successfully deleted event")

    except Exception as e:
        print(f"Application error: {e}")
    finally:
        db.close_connection()
        print("Database connection closed")


if __name__ == "__main__":
    main()
    main()
