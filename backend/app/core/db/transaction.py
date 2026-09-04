"""事务辅助:按需提交,失败回滚后原样抛出."""

from sqlalchemy.orm import Session


def commit_or_rollback(session: Session) -> None:
    """尝试提交;失败则回滚复位会话并原样抛出(绝不吞异常).

    - 成功:数据落库.
    - 失败:rollback 复位失效事务(session 可继续复用),再 raise,
      把失败如实暴露给调用方,避免假成功.
      业务错误翻译(如 IntegrityError → 40900 幂等回查)由 Service 层负责,
      通用层不做.
    """
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
