<?php

if (!defined('ABSPATH')) {
    exit;
}

function wrs_journal_path() {
    return wrs_storage_dir() . 'journal.ndjson';
}

function wrs_append_journal($entry) {
    $line = wp_json_encode($entry, JSON_UNESCAPED_SLASHES) . PHP_EOL;
    file_put_contents(wrs_journal_path(), $line, FILE_APPEND | LOCK_EX);
}

