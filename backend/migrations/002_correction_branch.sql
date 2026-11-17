
/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!50503 SET NAMES utf8mb4 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

-- 仪表纠偏：分支保留基线快照，BranchChange 仅记录分支内字段级修订，试算与正式训练隔离
DROP TABLE IF EXISTS `trials`;
CREATE TABLE `trials` (
  `id` int NOT NULL AUTO_INCREMENT,
  `branch_id` int NOT NULL,
  `features` json DEFAULT NULL,
  `alphas` json DEFAULT NULL,
  `state` varchar(20) NOT NULL,
  `result` json DEFAULT NULL,
  `error` text,
  PRIMARY KEY (`id`),
  KEY `branch_id` (`branch_id`),
  CONSTRAINT `trials_ibfk_1` FOREIGN KEY (`branch_id`) REFERENCES `correction_branches` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `branch_changes`;
CREATE TABLE `branch_changes` (
  `id` int NOT NULL AUTO_INCREMENT,
  `branch_id` int NOT NULL,
  `hour` varchar(30) NOT NULL,
  `field` varchar(30) NOT NULL,
  `old_value` float DEFAULT NULL,
  `new_value` float DEFAULT NULL,
  `reason` varchar(300) DEFAULT '',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_branch_hour_field` (`branch_id`,`hour`,`field`),
  KEY `branch_id` (`branch_id`),
  CONSTRAINT `branch_changes_ibfk_1` FOREIGN KEY (`branch_id`) REFERENCES `correction_branches` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

DROP TABLE IF EXISTS `correction_branches`;
CREATE TABLE `correction_branches` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(100) NOT NULL,
  `status` varchar(20) NOT NULL DEFAULT 'draft',
  `baseline` json NOT NULL,
  `baseline_checksum` varchar(80) DEFAULT NULL,
  `current_checksum` varchar(80) DEFAULT NULL,
  `features` json DEFAULT NULL,
  `alphas` json DEFAULT NULL,
  `trial_id` int DEFAULT NULL,
  `trial_result` json DEFAULT NULL,
  `error` text,
  `published_run_id` int DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- 正式 Run 记录发布来源，唯一约束保证一个分支最多产生一个正式版本（重试不重复发布）
ALTER TABLE `runs` ADD COLUMN `source_branch_id` int DEFAULT NULL;
ALTER TABLE `runs` ADD UNIQUE KEY `uq_run_source_branch` (`source_branch_id`);

/*!40101 SET SQL_NOTES=@OLD_SQL_NOTES */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
