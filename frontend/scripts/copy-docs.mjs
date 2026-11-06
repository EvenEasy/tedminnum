import { mkdirSync, copyFileSync, writeFileSync } from "node:fs";
mkdirSync("dist/docs-assets", { recursive: true });
for (const name of ["swagger-ui-bundle.js", "swagger-ui.css"]) {
  copyFileSync(
    `node_modules/swagger-ui-dist/${name}`,
    `dist/docs-assets/${name}`,
  );
}
writeFileSync(
  "dist/docs-assets/init.js",
  `window.onload = () => SwaggerUIBundle({url:'/api/openapi.json',dom_id:'#swagger-ui',persistAuthorization:false,tryItOutEnabled:false});`,
);
