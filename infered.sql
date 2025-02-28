CREATE TABLE `user` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  `username` varchar(256) NOT NULL COMMENT 'Unique username for the user',
  `hashedPass` varchar(256) NOT NULL COMMENT 'User''s hashed password',
  `salt` varchar(256) NOT NULL COMMENT 'Salt for password hashing',
  `isPublic` tinyint(1) NOT NULL DEFAULT '0' COMMENT 'Indicates if the user''s profile is public',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the user was created',
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Stores user information' ;
 CREATE TABLE `event` (
  `id` int NOT NULL AUTO_INCREMENT,
  `userId` int NOT NULL,
  `event_title` varchar(255) NOT NULL,
  `event_date` date NOT NULL,
  `createTime` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updateTime` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `userId` (`userId`),
  CONSTRAINT `event_ibfk_1` FOREIGN KEY (`userId`) REFERENCES `user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci ;
 CREATE TABLE `summary` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  `ownerId` int NOT NULL COMMENT 'Foreign key linking to User',
  `shareLink` varchar(256) NOT NULL COMMENT 'Unique link for sharing the summary',
  `path_to_summary` text NOT NULL COMMENT 'Path to the summary file or content',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was created',
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was last updated',
  PRIMARY KEY (`id`),
  UNIQUE KEY `shareLink` (`shareLink`),
  KEY `ownerId` (`ownerId`),
  CONSTRAINT `summary_ibfk_1` FOREIGN KEY (`ownerId`) REFERENCES `user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=1 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Stores summary details';
CREATE TABLE `permission` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  `summaryId` int NOT NULL COMMENT 'Foreign key linking to Summary',
  `userId` int NOT NULL COMMENT 'Foreign key linking to User',
  `permissionType` enum('view','edit','comment') NOT NULL COMMENT 'Type of permission',
  `createTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was created',
  `updateTime` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was last updated',
  PRIMARY KEY (`id`),
  KEY `summaryId` (`summaryId`),
  KEY `userId` (`userId`),
  CONSTRAINT `permission_ibfk_1` FOREIGN KEY (`summaryId`) REFERENCES `summary` (`id`),
  CONSTRAINT `permission_ibfk_2` FOREIGN KEY (`userId`) REFERENCES `user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='Manages permissions for summaries';
