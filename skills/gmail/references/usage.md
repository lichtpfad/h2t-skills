# Gmail Skill - Полная документация

Интеграция Gmail API для Claude Code - чтение, отправка, поиск писем и управление почтовым ящиком.

## Возможности

- **Чтение писем**: Список последних писем, детальное чтение, конвертация HTML → plain text, JSON экспорт
- **Поиск**: Полная поддержка Gmail search syntax, фильтры по дате, статусу, вложениям
- **Отправка**: Простые текстовые письма, вложения, чтение body из файла
- **Управление**: Просмотр labels, добавление/удаление labels, пометка как прочитанное/важное

## Установка

```bash
# Получите OAuth credentials:
# - Google Cloud Console → Gmail API → Enable
# - Create OAuth Client ID (Desktop app)
# - Download credentials.json → ~/.config/google-calendar-mcp/credentials.json
```

## Gmail Search Syntax

| Оператор | Описание | Пример |
|----------|----------|--------|
| `from:` | От кого | `from:curator@example.com` |
| `to:` | Кому | `to:me` |
| `subject:` | В теме | `subject:DOR accelerator` |
| `label:` | С label | `label:important` |
| `has:` | Имеет | `has:attachment` |
| `is:` | Статус | `is:unread` |
| `after:` | После даты | `after:2026/02/01` |
| `before:` | До даты | `before:2026/02/28` |
| `older_than:` | Старше | `older_than:7d` |
| `newer_than:` | Новее | `newer_than:1m` |

### Логические операторы

- AND: пробел между операторами
- OR: `from:user1 OR from:user2`
- NOT: `-subject:spam`
- Группировка: `(from:user1 OR from:user2) subject:meeting`

## Системные labels

- `INBOX` - входящие
- `UNREAD` - непрочитанное
- `STARRED` - с звездой
- `IMPORTANT` - важное
- `SENT` - отправленные
- `DRAFT` - черновики
- `SPAM` - спам
- `TRASH` - корзина

## Зависимости

```
google-auth
google-auth-httplib2
google-auth-oauthlib
google-api-python-client
python-dotenv
```

## Troubleshooting

**"Token expired or revoked"**
```bash
rm ~/.config/google-calendar-mcp/tokens.json
# Re-run gmail skill to trigger OAuth flow
```

**"Gmail API has not been used"**
- Google Cloud Console → APIs & Services → Library → Enable "Gmail API"

## Ссылки

- [Gmail API Documentation](https://developers.google.com/gmail/api)
- [Gmail Search Operators](https://support.google.com/mail/answer/7190)
- [OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
