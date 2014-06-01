#!/usr/bin/env python

mysql_schema = ["""
CREATE TABLE user
(
    user_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    registration_id VARCHAR(4096) NOT NULL
        COMMENT "According to google it can be up to 4k. oO",
    ctime DATETIME NOT NULL
        COMMENT "First time we seen him",
    ltime DATETIME NOT NULL
        COMMENT "Last time we've seen him",
    PRIMARY KEY (user_id),
    KEY `ri` (registration_id(767))
) ENGINE=InnoDB DEFAULT CHARSET=ascii COLLATE=ascii_bin
""",
"""
CREATE TABLE alias
(
    user_id INT UNSIGNED NOT NULL,
    alias VARCHAR(191) COMMENT "767 / 4, max length for index in utf8mb4",
    PRIMARY KEY (alias, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
""",
"""
CREATE TABLE message
(
    message_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    status ENUM ("todo", "done") DEFAULT "todo",
    number_of_failures INT NOT NULL DEFAULT 0
        COMMENT "Number of retry, can be used to compute exponential back-off",
    retry_after DATETIME NOT NULL
        COMMENT "Do not retry before this date, servers are busy.",
    message VARCHAR(4096) NOT NULL,
    PRIMARY KEY (message_id),
    KEY r_ra (status, retry_after)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
""",
"""
CREATE TABLE recipient
(
    message_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    gcm_error varchar(25) NULL COMMENT "In case of GCM error",
    gcm_message_id varchar(25) NULL COMMENT "In case of success",
    gcm_registration_id varchar(4096) NULL COMMENT "See Canonical IDs",
    PRIMARY KEY (message_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin
"""
]
