   # ------------------------------------------------------------------------
    # FILE SYSTEM TOOLS
    # ------------------------------------------------------------------------
    def 
    def overwrite_file(self, path: str, new_content: str) -> str:
        """Edit an existing file by overwriting it with new content.
        Creates the file if it does not exist."""
        try:
            path = sanitize_path(path)
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return f"Successfully edited file: {path}"
        except Exception as e:
            return f"[Error] Failed to edit file: {str(e)}"

    def read_file(self, path: str) -> str:
        """
        Read and return the contents of a file.
        Supports text files of any format.
        """
        try:
            path = sanitize_path(path)
            
            if not os.path.exists(path):
                return f"[Error] File not found: {path}"
            
            if not os.path.isfile(path):
                return f"[Error] Path is not a file: {path}"
            
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Add to memory
            m1 = self.agent.mem.add_session_memory(
                self.agent.sess.id, path, "file",
                metadata={"status": "active", "priority": "high"},
                labels=["File"], promote=True
            )
            m2 = self.agent.mem.attach_document(
                self.agent.sess.id, path, content,
                {"topic": "read_file", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Read")
            
            return truncate_output(content)
            
        except UnicodeDecodeError:
            return f"[Error] File is not a text file or has encoding issues: {path}"
        except Exception as e:
            return f"[Error] Failed to read file: {str(e)}"

    def write_file(self, filepath: str, content: str) -> str:
        """
        Write content to a file. Creates parent directories if needed.
        Overwrites existing files.
        """
        try:
            filepath = sanitize_path(filepath)
            
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Add to memory
            m1 = self.agent.mem.add_session_memory(
                self.agent.sess.id, filepath, "file",
                metadata={"status": "active", "priority": "high"},
                labels=["File"], promote=True
            )
            m2 = self.agent.mem.attach_document(
                self.agent.sess.id, filepath, content,
                {"topic": "write_file", "agent": "system"}
            )
            self.agent.mem.link(m1.id, m2.id, "Written")
            
            return f"Successfully wrote {len(content)} characters to {filepath}"
            
        except Exception as e:
            return f"[Error] Failed to write file: {str(e)}"
    
    def list_directory(self, path: str = ".") -> str:
        """
        List contents of a directory with file sizes and types.
        """
        try:
            path = sanitize_path(path)
            
            if not os.path.exists(path):
                return f"[Error] Directory not found: {path}"
            
            if not os.path.isdir(path):
                return f"[Error] Path is not a directory: {path}"
            
            items = []
            for item in sorted(os.listdir(path)):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    items.append(f"[DIR]  {item}/")
                else:
                    size = os.path.getsize(item_path)
                    items.append(f"[FILE] {item} ({size} bytes)")
            
            return "\n".join(items) if items else "[Empty directory]"
            
        except Exception as e:
            return f"[Error] Failed to list directory: {str(e)}"
    
    def search_files(self, path: str, pattern: str) -> str:
        """
        Search for files matching a pattern recursively.
        Pattern can be a glob pattern (*.py) or regex.
        """
        try:
            path = sanitize_path(path)
            matches = []
            
            for root, dirs, files in os.walk(path):
                for file in files:
                    if re.search(pattern, file) or file.endswith(pattern):
                        full_path = os.path.join(root, file)
                        size = os.path.getsize(full_path)
                        matches.append(f"{full_path} ({size} bytes)")
            
            return "\n".join(matches) if matches else f"No files matching '{pattern}' found"
            
        except Exception as e:
            return f"[Error] Failed to search files: {str(e)}"
    