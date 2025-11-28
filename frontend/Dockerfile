# Use a small, efficient web server image
FROM nginx:alpine

# Set workdir (optional, just for clarity)
WORKDIR /usr/share/nginx/html

# Remove default nginx static files
RUN rm -rf ./*

# Copy your frontend files (HTML, JS, CSS, etc.) into the nginx web root
# Adjust the path if your files are in a subfolder.
COPY . /usr/share/nginx/html

# Expose the HTTP port
EXPOSE 80

# nginx image already defines the default CMD:
# ["nginx", "-g", "daemon off;"]
# so we don't need to override it.

