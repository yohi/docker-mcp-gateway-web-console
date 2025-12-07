[日本語 (Japanese)](CHANGELOG.ja.md)

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of Docker MCP Gateway Console
- Bitwarden authentication with API key and master password support
- Container lifecycle management (create, start, stop, restart, delete)
- Real-time log streaming via WebSocket
- MCP server catalog browsing and installation
- Search and filter functionality for catalog
- MCP Inspector for analyzing server capabilities (Tools, Resources, Prompts)
- Gateway configuration editor with visual interface
- Secure secret injection using Bitwarden reference notation
- Session management with automatic timeout
- In-memory secret caching for performance
- Responsive UI with Tailwind CSS
- Comprehensive documentation
- E2E testing with Playwright
- Unit tests for frontend and backend
- Docker Compose development environment
- Production deployment configurations

### Security
- Secrets never written to disk
- Memory-only secret storage
- Automatic session expiration
- HTTPS support for production
- CORS configuration

## [1.0.0] - YYYY-MM-DD

### Added
- First stable release

---

## Version History

### Version Format

- **Major.Minor.Patch** (e.g., 1.2.3)
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes (backward compatible)

### Change Categories

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security improvements

---

## Future Releases

### Planned for v1.1.0
- [ ] Custom catalog source management
- [ ] Container resource usage metrics
- [ ] Notification system for container events
- [ ] Bulk container operations
- [ ] Export/import configurations

### Planned for v1.2.0
- [ ] Multi-user support
- [ ] Role-based access control
- [ ] Audit logging
- [ ] Container templates
- [ ] Scheduled container operations

### Planned for v2.0.0
- [ ] Kubernetes support
- [ ] Multi-host Docker management
- [ ] Advanced monitoring and alerting
- [ ] Plugin system
- [ ] API rate limiting

---

## Migration Guides

### Upgrading to v1.0.0

No migration needed for initial release.

---

## Support

For questions about releases:
- Check the [documentation](README.md)
- Review [closed issues](repository-url/issues?q=is%3Aissue+is%3Aclosed)
- Open a new issue if needed

---

[Unreleased]: https://github.com/username/repo/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/username/repo/releases/tag/v1.0.0
