-- MySQL dump 10.13  Distrib 8.0.30, for Win64 (x86_64)
--
-- Host: localhost    Database: finalproj
-- ------------------------------------------------------
-- Server version	8.0.30
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO,ANSI' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table "event"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "event" (
  "id" int NOT NULL AUTO_INCREMENT,
  "userId" int NOT NULL,
  "event_title" varchar(255) NOT NULL,
  "event_date" datetime NOT NULL,
  "createTime" timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  "updateTime" timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY ("id"),
  KEY "userId" ("userId"),
  CONSTRAINT "event_ibfk_1" FOREIGN KEY ("userId") REFERENCES "user" ("id") ON DELETE CASCADE
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "event"
--

INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (2,1,'Test Event','2025-01-23 00:00:00','2025-01-23 19:54:56','2025-01-23 19:54:56');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (3,1,'Test Event','2025-01-23 00:00:00','2025-01-23 19:55:53','2025-01-23 19:55:53');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (4,1,'Test Event','2025-01-23 00:00:00','2025-01-23 19:56:10','2025-01-23 19:56:10');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (5,1,'Test Event','2025-01-23 00:00:00','2025-01-23 19:59:06','2025-01-23 19:59:06');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (6,4,'IDK something important','2025-01-25 00:00:00','2025-01-23 21:25:59','2025-01-23 21:25:59');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (20,37,'יום הולדת שמח!','2025-08-08 00:00:00','2025-04-21 16:08:50','2025-04-21 16:08:50');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (21,37,'יום הולדת שמח!','2025-08-08 00:00:00','2025-04-21 16:09:42','2025-04-21 16:09:42');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (30,37,'123','2025-04-29 15:15:35','2025-04-29 12:15:38','2025-04-29 12:15:38');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (31,37,'432','2025-04-29 15:17:32','2025-04-29 12:17:35','2025-04-29 12:17:35');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (34,37,'cx','2025-04-29 15:19:39','2025-04-29 12:19:41','2025-04-29 12:19:41');
INSERT INTO "event" ("id", "userId", "event_title", "event_date", "createTime", "updateTime") VALUES (36,37,'dfs','2025-05-03 16:09:03','2025-05-03 13:09:13','2025-05-03 13:09:13');

--
-- Table structure for table "group"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "group" (
  "id" int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  "groupName" varchar(255) NOT NULL COMMENT 'Name of the group',
  "createTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of creation',
  PRIMARY KEY ("id")
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "group"
--


--
-- Table structure for table "group_membership"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "group_membership" (
  "id" int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  "groupId" int NOT NULL COMMENT 'Foreign key linking to Group',
  "userId" int NOT NULL COMMENT 'Foreign key linking to User',
  "createTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of membership creation',
  PRIMARY KEY ("id"),
  KEY "groupId" ("groupId"),
  KEY "userId" ("userId"),
  CONSTRAINT "group_membership_ibfk_1" FOREIGN KEY ("groupId") REFERENCES "group" ("id") ON DELETE CASCADE,
  CONSTRAINT "group_membership_ibfk_2" FOREIGN KEY ("userId") REFERENCES "user" ("id") ON DELETE CASCADE
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "group_membership"
--


--
-- Table structure for table "links"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "links" (
  "id" int NOT NULL AUTO_INCREMENT,
  "source_summary_id" int NOT NULL,
  "target_summary_id" int NOT NULL,
  "link_text" varchar(255) DEFAULT NULL,
  PRIMARY KEY ("id"),
  KEY "source_summary_id" ("source_summary_id"),
  KEY "target_summary_id" ("target_summary_id"),
  CONSTRAINT "links_ibfk_1" FOREIGN KEY ("source_summary_id") REFERENCES "summary" ("id") ON DELETE CASCADE,
  CONSTRAINT "links_ibfk_2" FOREIGN KEY ("target_summary_id") REFERENCES "summary" ("id") ON DELETE CASCADE
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "links"
--

INSERT INTO "links" ("id", "source_summary_id", "target_summary_id", "link_text") VALUES (38,36,26,'HtmlTest custom font');
INSERT INTO "links" ("id", "source_summary_id", "target_summary_id", "link_text") VALUES (39,36,22,'This is a title');
INSERT INTO "links" ("id", "source_summary_id", "target_summary_id", "link_text") VALUES (92,33,26,'HtmlTest custom font');
INSERT INTO "links" ("id", "source_summary_id", "target_summary_id", "link_text") VALUES (93,33,22,'This is a title');

--
-- Table structure for table "permission"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "permission" (
  "id" int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  "summaryId" int NOT NULL COMMENT 'Foreign key linking to Summary',
  "userId" int NOT NULL COMMENT 'Foreign key linking to User',
  "permissionType" enum('view','edit','comment') NOT NULL COMMENT 'Type of permission',
  "createTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was created',
  "updateTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the permission was last updated',
  PRIMARY KEY ("id"),
  KEY "summaryId" ("summaryId"),
  KEY "userId" ("userId"),
  CONSTRAINT "permission_ibfk_1" FOREIGN KEY ("summaryId") REFERENCES "summary" ("id"),
  CONSTRAINT "permission_ibfk_2" FOREIGN KEY ("userId") REFERENCES "user" ("id")
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "permission"
--

INSERT INTO "permission" ("id", "summaryId", "userId", "permissionType", "createTime", "updateTime") VALUES (1,28,38,'edit','2025-03-21 13:06:05','2025-03-21 13:06:05');
INSERT INTO "permission" ("id", "summaryId", "userId", "permissionType", "createTime", "updateTime") VALUES (2,30,37,'edit','2025-03-21 13:53:42','2025-03-21 13:53:42');

--
-- Table structure for table "summary"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "summary" (
  "id" int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  "ownerId" int NOT NULL COMMENT 'Foreign key linking to User',
  "shareLink" varchar(512) NOT NULL,
  "path_to_summary" text NOT NULL COMMENT 'Path to the summary file or content',
  "createTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was created',
  "updateTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Timestamp of when the summary was last updated',
  "font" varchar(512) DEFAULT NULL,
  PRIMARY KEY ("id"),
  UNIQUE KEY "shareLink" ("shareLink"),
  UNIQUE KEY "shareLink_2" ("shareLink"),
  KEY "ownerId" ("ownerId"),
  CONSTRAINT "summary_ibfk_1" FOREIGN KEY ("ownerId") REFERENCES "user" ("id")
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "summary"
--

INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (20,4,'what are u summarizing','data\\4\\what_are_u_summarizing.md','2025-01-23 21:04:28','2025-01-23 21:04:28',NULL);
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (21,4,'This is yet another','data\\4\\This_is_yet_another.md','2025-01-23 21:06:22','2025-01-23 21:06:22',NULL);
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (22,37,'This is a title','data\\37\\This_is_a_title.md','2025-02-28 12:26:15','2025-02-28 12:26:15',NULL);
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (23,37,'Second summary','data\\37\\Second_summary.md','2025-02-28 12:26:32','2025-02-28 12:26:32',NULL);
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (24,37,'Summary 3','data\\37\\Summary_3.md','2025-02-28 13:27:57','2025-02-28 13:27:57',NULL);
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (25,37,'HtmlTest custom font2','data\\37\\HTML_tester.md','2025-03-01 12:13:05','2025-04-15 11:32:22','Blackadder ITC');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (26,37,'HtmlTest custom font','data\\37\\HtmlTest_custom_font.md','2025-03-01 16:20:18','2025-03-01 16:20:18','Agency FB|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (27,37,'handwriting font - blackwider ','data\\37\\handwriting_font_-_blackwider_.md','2025-03-01 16:34:10','2025-03-01 16:34:10','Blackadder ITC|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (28,37,'another','data\\37\\another.md','2025-03-21 10:11:50','2025-03-21 10:11:50','@Microsoft JhengHei Light|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (29,38,'','data\\38\\.md','2025-03-21 13:07:01','2025-03-21 13:07:01','@Microsoft JhengHei Light||');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (30,38,'qwe love letter','data\\38\\qwe_love_letter.md','2025-03-21 13:53:29','2025-03-21 13:53:29','Blackadder ITC|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (32,37,'###link links\naaa','data\\37\\link_example.md','2025-04-15 10:55:39','2025-04-15 11:26:38','Blackadder ITC|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (33,37,'links','data\\37\\links.md','2025-04-15 11:22:58','2025-04-24 06:04:31','Microsoft JhengHei Light|');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (34,37,'asd_links','data\\37\\asd_links.md','2025-04-15 11:34:59','2025-04-15 11:34:59','Blackadder ITC||');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (35,37,'bb','data\\37\\bb.md','2025-04-18 13:04:47','2025-04-18 13:04:47','Blackadder ITC|||');
INSERT INTO "summary" ("id", "ownerId", "shareLink", "path_to_summary", "createTime", "updateTime", "font") VALUES (36,37,' ','data\\37\\_.md','2025-04-24 05:59:05','2025-04-24 05:59:05','8514oem|');

--
-- Table structure for table "user"
--

/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE "user" (
  "id" int NOT NULL AUTO_INCREMENT COMMENT 'Primary key, unique identifier',
  "username" varchar(256) NOT NULL COMMENT 'Unique username for the user',
  "hashedPass" varchar(256) NOT NULL COMMENT 'User''s hashed password',
  "salt" varchar(256) NOT NULL COMMENT 'Salt for password hashing',
  "isPublic" tinyint(1) NOT NULL DEFAULT '0' COMMENT 'Indicates if the user''s profile is public',
  "createTime" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp of when the user was created',
  PRIMARY KEY ("id"),
  UNIQUE KEY "username" ("username")
);
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table "user"
--

INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (1,'liad','hashed','sa',0,'2025-01-23 17:12:28');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (2,'asd','3178948c321491106860302ae5f2dca1dab3a40ba4d30bda7a1f382445f7858e','EkFLS4wn14QaEvMmzkTPuA==',0,'2025-01-23 17:14:06');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (3,'l','89ffe27b520fe72180aeeecc9b0dfeb9d9f88607c54b6073fd0cf9cd04c201c6','hgxOEtrHe8AwpvAQdRWsTQ==',0,'2025-01-23 17:14:29');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (4,'zxc','0e1461e651b9abd750f55eccf10c999cead49ed07a24f778c2ced7f1a5b700c1','myXs0SyFlZtWOxjEL9eTxQ==',0,'2025-01-23 17:17:00');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (5,'testuser_6a111c94','2e3fe7147c420e55e255c72b43f7f6135aefe2e13d6eb3d80834e5b63d9cc3e9','QUFBQQ==',0,'2025-01-23 17:32:26');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (6,'testuser_ee419040','de03651ef3b3ca6bd403f202b65f0856687b9e786518f2580b1653b4052c490f','QUFBQQ==',0,'2025-01-23 17:33:35');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (7,'testuser_67ba3661','97ecd165a9d41371f890351123cbd61283ddac44abf66f7f5a438baf283182b1','QUFBQQ==',0,'2025-01-23 17:33:59');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (8,'testuser_c384f030','4e065e11184495dcece0c937f7c743d06ab5227db54f698d429cfa54acd2463f','QUFBQQ==',0,'2025-01-23 17:34:47');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (9,'testuser_5125f24d','7d9adc8d04ee257f8957921f817d22a040ac8f086f7009f0e2f9396e1e88c470','QUFBQQ==',0,'2025-01-23 17:35:27');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (10,'testuser_bcda5401','5b180b621a8f9324c61b7df0101c7bb8ab2f4f1d487284c2d7cc4280d13b29da','QUFBQQ==',0,'2025-01-23 17:35:47');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (11,'testuser_73194dca','fcac5c92887d5d82ca4475a7dbd3f7678d40ffd451536e6a0cf1892d728fd1b1','QUFBQQ==',0,'2025-01-23 17:37:32');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (12,'testuser_b43330ba','97d8034c08338935f2aa6b28b9e58e3815164ac8df78b381091b438dfd5af299','QUFBQQ==',0,'2025-01-23 17:38:22');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (13,'testuser_6393fa48','22c8a7619ccf0c677795b237f8041ad1335c1747ecb48469e7788a164195a8fa','QUFBQQ==',0,'2025-01-23 17:38:35');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (14,'testuser_57521435','151402a57b889bf5b7062abc974921dc6cd850e3401b6794e084c89d08d3d9c2','QUFBQQ==',0,'2025-01-23 17:38:50');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (15,'testuser_51dad4c9','87104dd0051f65ded6532f66697f1313f56efb15a433b103955afb4eafcad71b','QUFBQQ==',0,'2025-01-23 17:39:26');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (16,'testuser_3505e03f','39aaf43630ba8eb4da0115ba03a01fa14ffc3ee76bc095c051cfec13f269641c','QUFBQQ==',0,'2025-01-23 17:40:07');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (17,'testuser_7212394b','516bd438baf65192ed93dd40ee0f34213dfaef4daa2fb190fd9c3302f9066f69','QUFBQQ==',0,'2025-01-23 17:40:19');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (18,'testuser_cb3572dd','daf7089f8f0c5cf3b3c57c7fd5ea3895d785b4f7604140615d351aa6f68a2bc7','QUFBQQ==',0,'2025-01-23 17:42:17');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (19,'testuser_7b434cc8','ff1b7930ab2aeef33f74c29454a9d88c7a76e41b6877578e6d049696cf54590b','QUFBQQ==',0,'2025-01-23 19:44:06');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (20,'testuser_5bd5fd3f','4644e4162380081a6fdd71525eeb4464159c7c49fd2d610f0b20f031125349c5','QUFBQQ==',0,'2025-01-23 19:44:26');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (21,'testuser_e3eed873','803c0e504829a2eb0621ecdf971d2fefd6d4d495cce05ef47d35ef9ee28318cc','QUFBQQ==',0,'2025-01-23 19:45:15');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (22,'testuser_7a4660b4','f6cf831b7b4f785ee2dd61a7977727e9e4acc0dc234a8566ec7849e0c3ba33a3','QUFBQQ==',0,'2025-01-23 19:46:42');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (23,'testuser_684af25a','d02a9070cea4b42591428f8736197d03ebbcf2c3c7c1e2ed83676e1b38e17684','QUFBQQ==',0,'2025-01-23 19:47:25');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (24,'testuser_ff81833d','ea9bdbe285ff8fcb67112f4154b2158bb4e1861ff5917a927a0e3f488c81ea26','QUFBQQ==',0,'2025-01-23 19:49:03');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (25,'testuser_1813334f','04f95451646975e8a3f22ea50a0173a108d1abed48e0da843d6b7c755f1e55cd','QUFBQQ==',0,'2025-01-23 19:51:10');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (26,'testuser_3cb5b688','2a64206057eb91e7bd1d143a2ebf62419136ef3f8d3ce5679387d072957aec65','QUFBQQ==',0,'2025-01-23 19:51:48');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (27,'testuser_753367ed','43ea4aaf5db4251f73b5e22c81e03b93ef15a19e1df3f69c085b672eb32e08dd','QUFBQQ==',0,'2025-01-23 19:52:01');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (28,'testuser_fd21b825','350f4840c6a618538014cc06845a43a5735eee89d7c7ff5da64a9538291474a0','QUFBQQ==',0,'2025-01-23 19:53:01');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (29,'testuser_05055935','c91eda87ec7203b3a15ba5803f2f18e533ef1b06890d135565b8cb85e91cccc0','QUFBQQ==',0,'2025-01-23 19:53:24');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (30,'testuser_95408ee7','e81671596fac2d77e76f4d0eb45d05cc7d0fea81779118d3c0526bff8400e916','QUFBQQ==',0,'2025-01-23 19:54:56');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (31,'testuser_286d1f3c','6e2cf5bb9b088bab97850e497d597d715310b91912bb690fe4e8edb0f6412fb1','QUFBQQ==',0,'2025-01-23 19:55:53');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (32,'testuser_b9a6e9b6','1499ca82f3581cdb08398d5c4a28cb9e59f60d8f63e6f665656e314cdd3421a3','QUFBQQ==',0,'2025-01-23 19:56:10');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (33,'testuser_e0f84ca4','66c269567a4c03e94bd7c01672a1aff5a0e4ed81ee7b22687430d1ee8de1ff73','QUFBQQ==',0,'2025-01-23 19:57:02');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (34,'testuser_97d13068','d1e43cd7df9cfb3442a3f7a39614f4e071bdad64a450b2db4043f9e8b5fd8b7e','QUFBQQ==',0,'2025-01-23 19:58:14');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (35,'testuser_61b538c5','bf67eb42c704371789dc32fb6b3ddddefcb8a72bdbb935c803e868c05737a4d1','QUFBQQ==',0,'2025-01-23 19:59:06');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (37,'qwe','a0e0849855b68777133f3f96d7778d399db2c7a55047aa50467067fb99f2ec64','ApuNno3Z9A8Cy4UjkM0TJg==',0,'2025-02-24 15:52:42');
INSERT INTO "user" ("id", "username", "hashedPass", "salt", "isPublic", "createTime") VALUES (38,'z','13d179ca3f49db9d6d3accac883636e99298b326c57377dcf1241466ba2933f2','lGM+x6EQkNyLOuJY8XpSXA==',0,'2025-03-21 13:02:51');
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-05-03 21:18:25
