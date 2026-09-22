-- ============================================================
-- 圖書館座位預約系統 MySQL 資料庫建立結構 (schema.sql)
-- ============================================================

-- 1. 建立資料庫 (若不存在)
CREATE DATABASE IF NOT EXISTS `library_db` 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE `library_db`;

-- 2. 建立使用者資料表 (users)
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` VARCHAR(20) NOT NULL UNIQUE COMMENT '學號(帳號)',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '加鹽雜湊密碼',
    `name` VARCHAR(50) DEFAULT NULL COMMENT '學生姓名',
    `role` VARCHAR(10) DEFAULT 'student' COMMENT '角色: student / admin',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- 3. 建立座位資料表 (seats)
CREATE TABLE IF NOT EXISTS `seats` (
    `id` INT PRIMARY KEY COMMENT '座位號碼 (1~10)',
    `status` VARCHAR(20) DEFAULT 'active' COMMENT '狀態: active / maintenance',
    `has_outlet` BOOLEAN DEFAULT TRUE COMMENT '是否有插座'
) ENGINE=InnoDB;

-- 預先填入 1~10 號座位 (若尚未填入)
INSERT IGNORE INTO `seats` (`id`, `status`, `has_outlet`) VALUES
(1, 'active', TRUE),
(2, 'active', TRUE),
(3, 'active', TRUE),
(4, 'active', TRUE),
(5, 'active', TRUE),
(6, 'active', TRUE),
(7, 'active', TRUE),
(8, 'active', TRUE),
(9, 'active', TRUE),
(10, 'active', TRUE);

-- 4. 建立預約紀錄資料表 (reservations)
CREATE TABLE IF NOT EXISTS `reservations` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL COMMENT '預約學生 ID',
    `seat_id` INT NOT NULL COMMENT '座位編號 (1~10)',
    `reservation_date` DATE NOT NULL COMMENT '預約日期',
    `start_time` TIME NOT NULL COMMENT '開始時間',
    `end_time` TIME NOT NULL COMMENT '結束時間',
    `duration` DECIMAL(3, 1) NOT NULL COMMENT '使用時長 (小時)',
    `status` VARCHAR(20) DEFAULT 'reserved' COMMENT '狀態: reserved / cancelled / completed',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 外鍵約束
    CONSTRAINT `fk_res_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_res_seat` FOREIGN KEY (`seat_id`) REFERENCES `seats` (`id`) ON DELETE CASCADE,
    
    -- 建立複合索引以加速查詢時段重疊與衝突檢測
    INDEX `idx_seat_schedule` (`seat_id`, `reservation_date`, `status`, `start_time`, `end_time`),
    INDEX `idx_user_res` (`user_id`, `reservation_date`)
) ENGINE=InnoDB;
