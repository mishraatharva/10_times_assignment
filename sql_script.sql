create database timesdb123;
use timesdb123;
show tables;
ALTER TABLE articles MODIFY title LONGTEXT;
ALTER TABLE articles MODIFY description LONGTEXT;
select * from articles;

drop table articles;