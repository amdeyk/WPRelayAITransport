CREATE TABLE `{prefix}wrs_migrations` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `migration_key` varchar(191) NOT NULL,
  `applied_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `migration_key` (`migration_key`)
);

CREATE TABLE `{prefix}wrs_email_templates` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `template_key` varchar(191) NOT NULL,
  `subject` text NOT NULL,
  `html_body` longtext NOT NULL,
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `template_key` (`template_key`)
);

CREATE TABLE `{prefix}wrs_send_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `template_key` varchar(191) NOT NULL,
  `recipient` varchar(191) NOT NULL,
  `status` varchar(50) NOT NULL,
  `sent_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `{prefix}wrs_form_submissions` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `form_key` varchar(191) NOT NULL,
  `payload_json` longtext NOT NULL,
  `submitted_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
);

CREATE TABLE `{prefix}wrs_cron_log` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT,
  `job_key` varchar(191) NOT NULL,
  `status` varchar(50) NOT NULL,
  `message` text NULL,
  `ran_at` datetime NOT NULL,
  PRIMARY KEY (`id`)
);
