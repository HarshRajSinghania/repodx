// Demo app for RepoDx. Every credential in this folder is fake.
const DATABASE_URL = "postgres://app_user:hunter2-fake@db.demo-host.dev:5432/app";
const port = process.env.PORT || 3000;

console.log(`Listening on ${port}`, DATABASE_URL.length);
