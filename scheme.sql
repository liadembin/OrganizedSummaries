-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS finalproj;
USE finalproj;

-- User table
CREATE TABLE `User` (
  `id` BINARY(16) PRIMARY KEY COMMENT 'Primary key, unique identifier',
  `username` varchar(256) UNIQUE NOT NULL COMMENT 'Unique username for the user',
  `hashedPass` varchar(256) NOT NULL COMMENT 'User''s hashed password',
  `salt` varchar(256) NOT NULL COMMENT 'Salt for password hashing',
  `isPublic` tinyint(1) NOT NULL DEFAULT 0 COMMENT 'Indicates if the user''s profile is public',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the user was created',
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the user was last updated'
) COMMENT 'Stores user information';

-- Summary table
CREATE TABLE `Summary` (
  `id` BINARY(16) PRIMARY KEY COMMENT 'Primary key, unique identifier',
  `ownerId` BINARY(16) NOT NULL COMMENT 'Foreign key linking to User',
  `shareLink` varchar(256) UNIQUE NOT NULL COMMENT 'Unique link for sharing the summary',
  `path_to_summary` text NOT NULL COMMENT 'Path to the summary file or content',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was created',
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was last updated',
  FOREIGN KEY (`ownerId`) REFERENCES `User` (`id`)
) COMMENT 'Stores summary details';

-- Permission table
CREATE TABLE `Permission` (
  `id` BINARY(16) PRIMARY KEY COMMENT 'Primary key, unique identifier',
  `summaryId` BINARY(16) NOT NULL COMMENT 'Foreign key linking to Summary',
  `userId` BINARY(16) NOT NULL COMMENT 'Foreign key linking to User',
  `permissionType` ENUM('view', 'edit', 'comment') NOT NULL COMMENT 'Type of permission',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was created',
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was last updated',
  FOREIGN KEY (`summaryId`) REFERENCES `Summary` (`id`),
  FOREIGN KEY (`userId`) REFERENCES `User` (`id`)
) COMMENT 'Manages permissions for summaries';
CREATE TABLE Event (
    id INT AUTO_INCREMENT PRIMARY KEY,
    userId INT NOT NULL,
    event_title VARCHAR(255) NOT NULL,
    event_date DATE NOT NULL,
    createTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updateTime TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (userId) REFERENCES user(id) ON DELETE CASCADE
);

