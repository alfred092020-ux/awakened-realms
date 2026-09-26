drop trigger if exists superbrain_event_wake_enqueue;
create trigger superbrain_event_wake_enqueue
after insert on brain_events
begin
  insert or ignore into brain_wake_queue(
    subscription_id,event_id,subscriber,state,attempts,available_epoch,
    created_at,updated_at
  )
  select
    s.subscription_id,new.id,s.subscriber,'PENDING',0,new.ts_epoch,
    new.ts,new.ts
  from brain_event_subscriptions s
  where s.enabled=1
    and new.event_type not in ('WAKE_FAILED','RECONCILIATION')
    and (s.event_type='*' or s.event_type=new.event_type)
    and new.priority <= s.priority_ceiling
    and (s.task_id is null or s.task_id=new.task_id)
    and (new.recipient='ALL' or new.recipient=s.subscriber)
    and s.subscriber <> new.sender;
end;
