/**
 * 转专业规则的数据加载。
 *
 * 两个 hook：
 *   useRuleList()  —— 有哪些规则文件（GET /api/rules）
 *   useRuleDoc()   —— 某一份规则的全文（GET /api/rules/{id}?category=）
 *
 * `useRuleDoc` 沿用 useValidation 的"失败不清空"：请求失败时**保留上一次的 doc**
 * 并置 stale。清空等于告诉用户"这一类没有规则" —— 那是比报错更危险的假阴性。
 * 切换类别时同样保留旧内容（只是降透明度），避免每点一次 chip 就闪一次白。
 */

import { useCallback, useEffect, useRef, useState } from 'react'

import { describeError } from '@/api/client'
import { getRule, getRules } from '@/api/endpoints'
import type { RuleCategory, RuleDoc, RuleSummary } from '@/api/types'

export type RuleListStatus = 'loading' | 'ready' | 'error'

export interface RuleListState {
  status: RuleListStatus
  items: RuleSummary[]
  error: string
  retry: () => void
}

export function useRuleList(): RuleListState {
  const [status, setStatus] = useState<RuleListStatus>('loading')
  const [items, setItems] = useState<RuleSummary[]>([])
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setStatus('loading')

    getRules({ signal: controller.signal })
      .then((response) => {
        if (controller.signal.aborted) return
        setItems(response.items)
        setStatus('ready')
        setError('')
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setStatus('error')
        setError(describeError(cause))
      })

    return () => controller.abort()
  }, [nonce])

  const retry = useCallback(() => setNonce((n) => n + 1), [])

  return { status, items, error, retry }
}

export type RuleDocStatus = 'idle' | 'loading' | 'ready' | 'error'

export interface RuleDocState {
  doc: RuleDoc | null
  status: RuleDocStatus
  error: string
  /** 曾经成功、现在失败 —— 打「已过期」而不是清空 */
  stale: boolean
  /** 请求在途：降透明度，不换骨架屏（避免切换类别时闪烁） */
  loading: boolean
  reload: () => void
}

export function useRuleDoc(
  ruleId: string | null,
  category: RuleCategory | null,
): RuleDocState {
  const [doc, setDoc] = useState<RuleDoc | null>(null)
  const [status, setStatus] = useState<RuleDocStatus>('idle')
  const [error, setError] = useState('')
  const [nonce, setNonce] = useState(0)
  const seqRef = useRef(0)

  useEffect(() => {
    if (!ruleId) {
      setDoc(null)
      setStatus('idle')
      setError('')
      return
    }

    const controller = new AbortController()
    const mine = ++seqRef.current
    setStatus('loading')
    setError('')

    getRule(ruleId, category, { signal: controller.signal })
      .then((next) => {
        if (mine !== seqRef.current) return // 后发先至守卫
        if (controller.signal.aborted) return
        setDoc(next)
        setStatus('ready')
        setError('')
      })
      .catch((cause: unknown) => {
        if (mine !== seqRef.current) return
        if (controller.signal.aborted) return
        setStatus('error')
        setError(describeError(cause))
        // 刻意不动 doc —— 保住上一次的规则全文
      })

    return () => controller.abort()
  }, [ruleId, category, nonce])

  const reload = useCallback(() => setNonce((n) => n + 1), [])

  return {
    doc,
    status,
    error,
    stale: status === 'error' && doc !== null,
    loading: status === 'loading',
    reload,
  }
}
